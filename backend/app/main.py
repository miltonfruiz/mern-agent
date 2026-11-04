import os
import io
import json
import zipfile
import shutil
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from app.agent import agente, llm
from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt
from pymongo import MongoClient
from bson import ObjectId
import os
import urllib.request
import urllib.error
import httpx
import subprocess
import tempfile
import asyncio

#Función de validación con Node.js
def limpiar_markdown(contenido: str) -> str:
    contenido = contenido.strip()
    if contenido.startswith("```"):
        lineas = contenido.split("\n")
        lineas = lineas[1:]
        if lineas and lineas[-1].strip().startswith("```"):
            lineas = lineas[:-1]
        contenido = "\n".join(lineas)
    return contenido.strip()

def validar_sintaxis_js(contenido: str) -> tuple[bool, str]:
    """Valida sintaxis JS/JSX usando node --check. Retorna (es_valido, error)."""
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(contenido)
            temp_path = f.name

        resultado = subprocess.run(
            ["node", "--check", temp_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        os.unlink(temp_path)

        if resultado.returncode == 0:
            return True, ""
        return False, resultado.stderr[:300]
    except Exception as e:
        return True, ""  # si node falla por otra razón, no bloqueamos

def validar_sintaxis_ts(contenido: str) -> tuple[bool, str]:
    """Valida balance de llaves/paréntesis para TS/TSX (node --check no soporta JSX/TS)."""
    pares = {"(": ")", "{": "}", "[": "]"}
    cierres = {")": "(", "}": "{", "]": "["}
    stack = []
    en_string = None
    i = 0
    while i < len(contenido):
        c = contenido[i]
        if en_string:
            if c == "\\":
                i += 2
                continue
            if c == en_string:
                en_string = None
        elif c in ("'", '"', "`"):
            en_string = c
        elif c in pares:
            stack.append(c)
        elif c in cierres:
            if not stack or stack[-1] != cierres[c]:
                return False, f"Desbalance de '{c}' cerca de la posición {i}"
            stack.pop()
        i += 1
    if stack:
        return False, f"Faltan cerrar: {stack}"
    if en_string:
        return False, "String/template literal sin cerrar"
    return True, ""

def validar_json(contenido: str) -> tuple[bool, str]:
    try:
        json.loads(contenido)
        return True, ""
    except json.JSONDecodeError as e:
        return False, str(e)[:200]

def validar_codigo(contenido: str, archivo: str) -> tuple[bool, str]:
    if archivo.endswith(".json"):
        return validar_json(contenido)
    if archivo.endswith((".js",)):
        return validar_sintaxis_js(contenido)
    if archivo.endswith((".ts", ".tsx", ".jsx")):
        return validar_sintaxis_ts(contenido)
    return True, ""

# MongoDB conexión
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["mern_agent"]
users_collection = db["users"]

# JWT config
SECRET_KEY = os.getenv("JWT_SECRET", "supersecretkey123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

# Password hashing
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def crear_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verificar_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────
class DeployRender(BaseModel):
    nombre_proyecto: str
    repo_url: str

class ExportGithub(BaseModel):
    nombre_proyecto: str

class MensajeContexto(BaseModel):
    rol: str
    contenido: str

class NuevoProyecto(BaseModel):
    instrucciones: str
    contexto: list[MensajeContexto] = []
    proyecto_activo: Optional[str] = None

class AnalisisRepo(BaseModel):
    repo_url: str

class GuardarArchivo(BaseModel):
    contenido: str

class GenerarTests(BaseModel):
    nombre_proyecto: str
    instrucciones: str

class RegisterData(BaseModel):
    nombre: str
    email: str
    password: str

class LoginData(BaseModel):
    email: str
    password: str

# ─────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "MERN Agent corriendo"}

@app.post("/generar")
def generar_proyecto(data: NuevoProyecto):
    resultado = agente.invoke({
        "instrucciones": data.instrucciones,
        "nombre_proyecto": data.proyecto_activo or "",
        "archivos_generados": [],
        "mensaje_final": "",
        "modo": "nuevo",
        "repo_url": None,
        "analisis": None,
    })
    return {
        "proyecto": resultado["nombre_proyecto"],
        "archivos": resultado["archivos_generados"],
        "mensaje": resultado["mensaje_final"]
    }

@app.post("/generar/stream")
async def generar_stream(data: NuevoProyecto):
    async def event_stream():

        # Construir historial de contexto para el LLM
        historial = ""
        if data.contexto:
            historial = "\n\nHistorial de la conversación:\n"
            for msg in data.contexto[-6:]:  # últimos 6 mensajes
                rol = "Cliente" if msg.rol == "user" else "Agente"
                historial += f"{rol}: {msg.contenido}\n"

        # Detectar si es modificación de proyecto existente
        es_modificacion = data.proyecto_activo and data.proyecto_activo != ""

        if es_modificacion:
            yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'🔄 Modificando proyecto existente: {data.proyecto_activo}...'})}\n\n"
        else:
            yield f"data: {json.dumps({'tipo': 'estado', 'texto': '🔍 Analizando instrucciones del cliente...'})}\n\n"

        # Determinar nombre del proyecto
        if es_modificacion:
            nombre = data.proyecto_activo
        else:
            prompt_nombre = f"""
            Eres un arquitecto de software MERN experto.
            {historial}
            El cliente quiere: {data.instrucciones}
            Respondé SOLO con el nombre del proyecto en una palabra, en minúsculas.
            """
            nombre = llm.invoke(prompt_nombre).content.strip()

        yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'📁 Proyecto: {nombre}'})}\n\n"

        # Generar contrato de API (solo para proyectos nuevos)
        contrato_api = ""
        if not es_modificacion:
            yield f"data: {json.dumps({'tipo': 'estado', 'texto': '📋 Diseñando contrato de API...'})}\n\n"
            prompt_contrato = f"""You are a senior backend architect.
Project: {data.instrucciones}

Design a REST API contract for this project. List ONLY the endpoints needed.
Respond ONLY with valid JSON in this exact format, no markdown, no explanation:
{{
  "port": 5000,
  "mongoUri": "process.env.MONGO_URI",
  "endpoints": [
    {{"method": "POST", "path": "/api/auth/register", "description": "register a new user"}},
    {{"method": "POST", "path": "/api/auth/login", "description": "login user"}},
    {{"method": "GET", "path": "/api/items", "description": "list items", "auth": true}},
    {{"method": "POST", "path": "/api/items", "description": "create item", "auth": true}}
  ],
  "mainModel": {{"name": "Item", "fields": ["field1: String", "field2: Number"]}}
}}
All paths must start with /api/. Include auth routes plus the main CRUD routes for this specific project.
"""
            contrato_raw = llm.invoke(prompt_contrato).content
            contrato_raw = limpiar_markdown(contrato_raw)
            try:
                contrato_json = json.loads(contrato_raw)
                contrato_api = json.dumps(contrato_json, indent=2)
            except:
                contrato_api = contrato_raw

            yield f"data: {json.dumps({'tipo': 'estado', 'texto': '✅ Contrato de API definido'})}\n\n"

        # Determinar qué archivos generar según el contexto
        prompt_plan = f"""
        Eres un arquitecto de software MERN experto.
        {historial}
        
        Proyecto actual: {nombre}
        Nueva instrucción del cliente: {data.instrucciones}
        Es modificación de proyecto existente: {es_modificacion}
        
        Analizá la instrucción y respondé SOLO con una lista JSON de archivos a generar/modificar.
        Ejemplo: ["backend/routes/reportRoutes.js", "backend/controllers/reportController.js"]
        
        Si es un proyecto nuevo, incluí todos los archivos base.
        Si es una modificación, incluí SOLO los archivos afectados por el cambio.
        SOLO el JSON, sin explicaciones.
        """
        plan_raw = llm.invoke(prompt_plan).content.strip()

        # Limpiar respuesta JSON
        try:
            plan_raw = plan_raw.replace("```json", "").replace("```", "").strip()
            archivos_plan = json.loads(plan_raw)
        except:
            archivos_plan = []

        # Estructura fija de nombres de archivo (evita que el LLM invente nombres)
        estructura_archivos = """
FIXED FILE STRUCTURE (you MUST use these exact relative require paths, never invent different names):
- ./models/User.js (exports User model)
- ./models/Model.js (exports main model)
- ./middleware/auth.js (exports authenticate middleware function)
- ./middleware/validate.js (exports validation middleware)
- ./controllers/authController.js (exports register, login, logout functions)
- ./controllers/controller.js (exports CRUD functions for the main resource)
- ./routes/authRoutes.js (requires ../controllers/authController and ../middleware/validate)
- ./routes/routes.js (requires ../controllers/controller and ../middleware/auth)
- server.js requires ./routes/authRoutes and ./routes/routes
"""

        # Si es proyecto nuevo usar archivos base completos
        if not es_modificacion:
            archivos_a_generar = [
                ("backend/middleware/auth.js", """Generate ONLY middleware/auth.js with JWT verification.
Export EXACTLY ONE middleware function that can be used directly in routes like: router.get('/path', authenticate, controller.fn)

The file must look exactly like this pattern:

const jwt = require('jsonwebtoken');

const authenticate = (req, res, next) => {
  const authHeader = req.header('Authorization');
  if (!authHeader) {
    return res.status(401).json({ message: 'No token provided' });
  }
  const token = authHeader.replace('Bearer ', '');
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.userId = decoded.userId;
    next();
  } catch (err) {
    return res.status(401).json({ message: 'Invalid token' });
  }
};

module.exports = authenticate;

Do NOT export an object. Do NOT export { authenticate }. Export ONLY the single function directly with module.exports = authenticate.
ONLY JS code, NO markdown."""),
                ("backend/middleware/validate.js", """Generate ONLY middleware/validate.js using express-validator.
Export EXACTLY ONE middleware function that can be used directly in routes like: router.post('/path', validate, controller.fn)

The file must look exactly like this pattern (adapt only the validation rules):

const { body, validationResult } = require('express-validator');

const validate = (req, res, next) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(422).json({ errors: errors.array() });
  }
  next();
};

module.exports = validate;

Do NOT export an object. Do NOT export a function factory. Export ONLY the single middleware function shown above (you may add body() validation rules as a separate array exported alongside if truly needed, but the main export used in routes MUST be a single callable middleware function named validate, exported directly with module.exports = validate).
ONLY JS code, NO markdown."""),
                ("backend/models/User.js", """Generate ONLY models/User.js with Mongoose.
Include email, hashed password, role, comparePassword method, pre-save hook.
CRITICAL: use EXACTLY require('bcryptjs') — NOT require('bcrypt'). The package is bcryptjs with 'js' at the end.
Export with module.exports = mongoose.model('User', schema).
ONLY JS code, NO markdown."""),
                ("backend/models/Model.js", f"""Generate ONLY the main Mongoose model for: {data.instrucciones}

API CONTRACT (use mainModel fields):
{contrato_api}

Export with module.exports = mongoose.model('ModelName', schema).
ONLY JS code, NO markdown."""),
                ("backend/controllers/authController.js", f"""Generate ONLY controllers/authController.js.
{estructura_archivos}
It must require the User model with: const User = require('../models/User');
CRITICAL: use EXACTLY require('bcryptjs') — NOT require('bcrypt'). The package is bcryptjs with 'js' at the end.

Define EXACTLY three async functions, each with signature (req, res):
async function register(req, res) {{ ... }}
async function login(req, res) {{ ... }}
async function logout(req, res) {{ ... }}

Each function must be a plain function, NOT an object, NOT an arrow function assigned weirdly.
End the file with EXACTLY: module.exports = {{ register, login, logout }};

Use bcryptjs and jsonwebtoken (process.env.JWT_SECRET).
ONLY JS code, NO markdown."""),
                ("backend/controllers/controller.js", f"""Generate ONLY controllers/controller.js with CRUD functions matching this API CONTRACT:
{contrato_api}

{estructura_archivos}
It must require the main model with: const Model = require('../models/Model');

You MUST use EXACTLY these function names (no variations, no custom names):
async function getAll(req, res) {{ ... }}
async function getOne(req, res) {{ ... }}
async function create(req, res) {{ ... }}
async function update(req, res) {{ ... }}
async function remove(req, res) {{ ... }}

End the file with EXACTLY this line:
module.exports = {{ getAll, getOne, create, update, remove }};

Do NOT use any other function names. routes.js will import exactly: controller.getAll, controller.getOne, controller.create, controller.update, controller.remove
ONLY JS code, NO markdown."""),
                ("frontend/src/App.tsx", f"""Generate ONLY valid TypeScript React code for App.tsx.
Project: {data.instrucciones}

API CONTRACT:
{contrato_api}

You MUST follow this EXACT component structure with these EXACT className values (Tailwind classes):

import React, {{ useState, useEffect }} from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

interface MainModel {{
  _id: string;
  // ADD fields from mainModel here based on the API CONTRACT
}}

export default function App() {{
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [items, setItems] = useState<MainModel[]>([]);
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [error, setError] = useState('');
  // ADD state for create form fields based on the model

  const authHeaders = {{
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/json'
  }};

  useEffect(() => {{ if (token) fetchItems(); }}, [token]);

  const fetchItems = async () => {{
    // FILL: GET request to correct endpoint from contract
  }};

  const handleLogin = async () => {{
    const res = await fetch(`${{API_URL}}/api/auth/login`, {{
      method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ email: loginEmail, password: loginPassword }})
    }});
    const data = await res.json();
    if (res.ok) {{ localStorage.setItem('token', data.token); setToken(data.token); setError(''); }}
    else setError(data.message || 'Login failed');
  }};

  const handleRegister = async () => {{
    const res = await fetch(`${{API_URL}}/api/auth/register`, {{
      method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ email: registerEmail, password: registerPassword }})
    }});
    const data = await res.json();
    if (res.ok) {{ localStorage.setItem('token', data.token); setToken(data.token); setError(''); }}
    else setError(data.message || 'Register failed');
  }};

  const handleLogout = () => {{ localStorage.removeItem('token'); setToken(null); setItems([]); }};

  const handleCreate = async () => {{
    // FILL: POST to correct endpoint with form data from contract
  }};

  const handleDelete = async (id: string) => {{
    // FILL: DELETE to correct endpoint
  }};

  if (!token) return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-2xl p-8 w-full max-w-md shadow-2xl">
        <h1 className="text-3xl font-bold text-white text-center mb-1">Welcome</h1>
        <p className="text-slate-400 text-sm text-center mb-6">Sign in or create an account</p>
        {{error && <p className="text-red-400 text-sm text-center mb-4 bg-red-900/20 border border-red-800 rounded-lg p-2">{{error}}</p>}}
        <div className="flex flex-col gap-6">
          <div>
            <h2 className="text-lg font-semibold text-slate-200 mb-3 pb-2 border-b border-slate-700">Login</h2>
            <div className="flex flex-col gap-3">
              <input className="bg-slate-700 border border-slate-600 text-slate-200 placeholder-slate-400 rounded-lg px-4 py-2.5 w-full outline-none focus:border-blue-500 transition-all" type="email" placeholder="Email" value={{loginEmail}} onChange={{e => setLoginEmail(e.target.value)}} />
              <input className="bg-slate-700 border border-slate-600 text-slate-200 placeholder-slate-400 rounded-lg px-4 py-2.5 w-full outline-none focus:border-blue-500 transition-all" type="password" placeholder="Password" value={{loginPassword}} onChange={{e => setLoginPassword(e.target.value)}} />
              <button className="bg-blue-600 hover:bg-blue-500 text-white font-medium px-4 py-2.5 rounded-lg transition-all w-full" onClick={{handleLogin}}>Login</button>
            </div>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-slate-200 mb-3 pb-2 border-b border-slate-700">Register</h2>
            <div className="flex flex-col gap-3">
              <input className="bg-slate-700 border border-slate-600 text-slate-200 placeholder-slate-400 rounded-lg px-4 py-2.5 w-full outline-none focus:border-blue-500 transition-all" type="email" placeholder="Email" value={{registerEmail}} onChange={{e => setRegisterEmail(e.target.value)}} />
              <input className="bg-slate-700 border border-slate-600 text-slate-200 placeholder-slate-400 rounded-lg px-4 py-2.5 w-full outline-none focus:border-blue-500 transition-all" type="password" placeholder="Password" value={{registerPassword}} onChange={{e => setRegisterPassword(e.target.value)}} />
              <button className="bg-blue-600 hover:bg-blue-500 text-white font-medium px-4 py-2.5 rounded-lg transition-all w-full" onClick={{handleRegister}}>Register</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-900 p-6">
      <nav className="bg-slate-800 border border-slate-700 rounded-xl px-6 py-4 flex items-center justify-between mb-6 shadow-lg">
        <h1 className="text-xl font-bold text-white">PROJECT_NAME_HERE</h1>
        <button className="bg-slate-700 hover:bg-slate-600 text-slate-200 font-medium px-4 py-2 rounded-lg transition-all" onClick={{handleLogout}}>Logout</button>
      </nav>

      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 shadow-lg mb-6">
        <h2 className="text-lg font-bold text-white mb-4 pb-3 border-b border-slate-700">Create New</h2>
        <div className="flex flex-wrap gap-3 items-end">
          {{/* FILL: one input per model field with className="bg-slate-700 border border-slate-600 text-slate-200 placeholder-slate-400 rounded-lg px-4 py-2.5 outline-none focus:border-blue-500 transition-all" */}}
          <button className="bg-blue-600 hover:bg-blue-500 text-white font-medium px-4 py-2.5 rounded-lg transition-all" onClick={{handleCreate}}>Create</button>
        </div>
      </div>

      <div className="bg-slate-800 border border-slate-700 rounded-xl shadow-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-700">
          <h2 className="text-lg font-bold text-white">Items</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-slate-300">
            <thead className="bg-slate-700 text-slate-200 text-xs uppercase">
              <tr>
                {{/* FILL: one <th className="px-6 py-3 text-left"> per model field */}}
                <th className="px-6 py-3 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {{items.map(item => (
                <tr key={{item._id}} className="border-b border-slate-700 hover:bg-slate-750 transition-colors">
                  {{/* FILL: one <td className="px-6 py-4"> per model field */}}
                  <td className="px-6 py-4">
                    <button className="bg-red-600 hover:bg-red-500 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-all" onClick={{() => handleDelete(item._id)}}>Delete</button>
                  </td>
                </tr>
              ))}}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}}

INSTRUCTIONS:
1. Keep ALL className values EXACTLY as shown — do NOT simplify or remove any class
2. Fill in project-specific parts: interface fields, state, fetchItems, handleCreate, handleDelete, form inputs, table columns
3. Replace PROJECT_NAME_HERE with the actual project name from the instructions
4. Add state variables for each form field based on the mainModel in the API CONTRACT
5. ONLY pure TSX code, NO markdown, NO explanations
"""),
                ("backend/.env.example", "Generate ONLY .env.example with MONGO_URI, JWT_SECRET, JWT_EXPIRES_IN, PORT, NODE_ENV, CORS_ORIGIN. ONLY content, NO markdown."),
                ("README.md", f"""Generate ONLY README.md for: {data.instrucciones}
Include stack, installation, Docker, and this exact endpoint list:
{contrato_api}
Include security section. ONLY markdown."""),
            ]

        else:
            # Solo generar archivos del plan para modificaciones
            archivos_a_generar = []
            for archivo in archivos_plan:
                prompt_archivo = f"""
                Contexto del proyecto: {data.instrucciones}
                {historial}
                
                Generá SOLO el código para el archivo: {archivo}
                Instrucción específica: {data.instrucciones}
                SOLO código, sin explicaciones ni markdown.
                """
                archivos_a_generar.append((archivo, prompt_archivo))

        # Crear estructura de carpetas
        base_path = f"./proyectos/{nombre}"
        for carpeta in [
            f"{base_path}/backend/models",
            f"{base_path}/backend/routes",
            f"{base_path}/backend/controllers",
            f"{base_path}/backend/middleware",
            f"{base_path}/frontend/src/components",
            f"{base_path}/frontend/src/pages",
            f"{base_path}/frontend/src/store",
            f"{base_path}/frontend/public",
        ]:
            os.makedirs(carpeta, exist_ok=True)

        archivos_generados = []

        # Generar archivos
        for archivo, prompt in archivos_a_generar:
            yield f"data: {json.dumps({'tipo': 'archivo', 'texto': f'⚙️ Generando {archivo}...'})}\n\n"

            intentos = 0
            max_intentos = 3
            contenido = ""
            es_valido = False
            error_msg = ""

            while intentos < max_intentos and not es_valido:
                intentos += 1

                if intentos == 1:
                    prompt_actual = prompt
                else:
                    prompt_actual = f"""{prompt}

IMPORTANTE: El intento anterior generó código con este error de sintaxis:
{error_msg}

Corregí el error y generá el código completo y válido de nuevo.
NO uses bloques markdown (```), solo código puro.
"""

                contenido = llm.invoke(prompt_actual).content
                contenido = limpiar_markdown(contenido)

                es_valido, error_msg = validar_codigo(contenido, archivo)

                if not es_valido and intentos < max_intentos:
                    yield f"data: {json.dumps({'tipo': 'archivo', 'texto': f'⚠️ Error de sintaxis en {archivo}, reintentando ({intentos}/{max_intentos})...'})}\n\n"

            ruta_completa = f"{base_path}/{archivo}"
            os.makedirs(os.path.dirname(ruta_completa), exist_ok=True)
            with open(ruta_completa, "w", encoding="utf-8") as f:
                f.write(contenido)
            archivos_generados.append(archivo)

            if es_valido:
                yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': f'✅ {archivo}'})}\n\n"
            else:
                yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': f'⚠️ {archivo} (con posibles errores, revisar)'})}\n\n"
        
        # authRoutes.js FIJO — estructura determinística, no depende del LLM
        auth_routes_code = """const express = require('express');
const router = express.Router();
const authController = require('../controllers/authController');
const validate = require('../middleware/validate');

router.post('/register', validate, authController.register);
router.post('/login', validate, authController.login);
router.post('/logout', authController.logout);

module.exports = router;
"""
        with open(f"{base_path}/backend/routes/authRoutes.js", "w") as f:
            f.write(auth_routes_code)
        archivos_generados.append("backend/routes/authRoutes.js")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ backend/routes/authRoutes.js'})}\n\n"

        # server.js FIJO — estructura determinística
        server_code = f"""const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const dotenv = require('dotenv');
dotenv.config();

const authRoutes = require('./routes/authRoutes');
const routes = require('./routes/routes');

const app = express();
const PORT = process.env.PORT || 5000;

app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(rateLimit({{ windowMs: 15 * 60 * 1000, max: 100 }}));

app.use('/api/auth', authRoutes);
app.use('/api/{nombre}', routes);

app.get('/', (req, res) => res.json({{ status: 'ok', project: '{nombre}' }}));

mongoose.connect(process.env.MONGO_URI)
  .then(() => console.log('MongoDB connected'))
  .catch((err) => console.log('MongoDB error: ' + err.message));

app.listen(PORT, () => console.log('Server running on port ' + PORT));
"""
        with open(f"{base_path}/backend/server.js", "w") as f:
            f.write(server_code)
        archivos_generados.append("backend/server.js")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ backend/server.js'})}\n\n"

        # routes.js FIJO — estructura determinística, no depende del LLM
        routes_code = """const express = require('express');
const router = express.Router();
const controller = require('../controllers/controller');
const authenticate = require('../middleware/auth');

router.get('/', authenticate, controller.getAll);
router.get('/:id', authenticate, controller.getOne);
router.post('/', authenticate, controller.create);
router.put('/:id', authenticate, controller.update);
router.delete('/:id', authenticate, controller.remove);

module.exports = router;
"""
        with open(f"{base_path}/backend/routes/routes.js", "w") as f:
            f.write(routes_code)
        archivos_generados.append("backend/routes/routes.js")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ backend/routes/routes.js'})}\n\n"
        # package.json backend fijo y confiable
        pkg_backend = f"""{{
            "name": "{nombre}-backend",
            "version": "1.0.0",
            "main": "server.js",
            "scripts": {{
                "start": "node server.js",
                "dev": "nodemon server.js"
            }},
            "dependencies": {{
            "express": "^4.18.2",
            "mongoose": "^7.6.3",
            "cors": "^2.8.5",
            "dotenv": "^16.3.1",
            "jsonwebtoken": "^9.0.2",
            "bcryptjs": "^2.4.3",
            "helmet": "^7.1.0",
            "express-rate-limit": "^7.1.5",
            "express-validator": "^7.0.1"
            }},
            "devDependencies": {{
                "nodemon": "^3.0.2"
            }}
        }}"""
        with open(f"{base_path}/backend/package.json", "w") as f:
            f.write(pkg_backend)
        archivos_generados.append("backend/package.json")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ backend/package.json'})}\n\n"

        # package.json frontend fijo y confiable
        pkg_frontend = f"""{{
            "name": "{nombre}-frontend",
            "version": "0.0.0",
            "type": "module",
            "scripts": {{
                "dev": "vite",
                "build": "tsc && vite build",
                "preview": "vite preview"
            }},
            "dependencies": {{
                "react": "^18.2.0",
                "react-dom": "^18.2.0",
                "axios": "^1.6.2",
                "zustand": "^4.4.7"
            }},
            "devDependencies": {{
                "@types/react": "^18.2.43",
                "@types/react-dom": "^18.2.17",
                "@vitejs/plugin-react": "^4.2.1",
                "typescript": "^5.2.2",
                "vite": "^5.0.8",
                "tailwindcss": "^3.3.6",
                "autoprefixer": "^10.4.16",
                "postcss": "^8.4.32"
            }}
        }}"""
        with open(f"{base_path}/frontend/package.json", "w") as f:
            f.write(pkg_frontend)
        archivos_generados.append("frontend/package.json")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ frontend/package.json'})}\n\n"

        # vite.config.ts fijo
        vite_config = """import { defineConfig } from 'vite'
        import react from '@vitejs/plugin-react'

        export default defineConfig({
            plugins: [react()],
            server: {
                port: 5173,
            },
            build: {
                outDir: 'dist',
            },
        })
        """
        with open(f"{base_path}/frontend/vite.config.ts", "w") as f:
            f.write(vite_config)
        archivos_generados.append("frontend/vite.config.ts")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ frontend/vite.config.ts'})}\n\n"

        # index.html fijo
        index_html = f"""<!doctype html>
        <html lang="en">
            <head>
                <meta charset="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <title>{nombre}</title>
            </head>
            <body>
                <div id="root"></div>
                <script type="module" src="/src/main.tsx"></script>
            </body>
        </html>
        """
        with open(f"{base_path}/frontend/index.html", "w") as f:
            f.write(index_html)
        archivos_generados.append("frontend/index.html")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ frontend/index.html'})}\n\n"

        # main.tsx fijo
        main_tsx = """import { StrictMode } from 'react'
        import { createRoot } from 'react-dom/client'
        import './index.css'
        import App from './App.tsx'

        createRoot(document.getElementById('root')!).render(
            <StrictMode>
                <App />
            </StrictMode>,
        )
        """
        with open(f"{base_path}/frontend/src/main.tsx", "w") as f:
            f.write(main_tsx)
        archivos_generados.append("frontend/src/main.tsx")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ frontend/src/main.tsx'})}\n\n"

        # vite-env.d.ts fijo (tipado de variables de entorno)
        vite_env = """/// <reference types="vite/client" />

        interface ImportMetaEnv {
            readonly VITE_API_URL: string
        }

        interface ImportMeta {
            readonly env: ImportMetaEnv
        }
        """
        with open(f"{base_path}/frontend/src/vite-env.d.ts", "w") as f:
            f.write(vite_env)
        archivos_generados.append("frontend/src/vite-env.d.ts")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ frontend/src/vite-env.d.ts'})}\n\n"

        # index.css fijo sin @apply
        index_css = """@tailwind base;
@tailwind components;
@tailwind utilities;

* { margin: 0; padding: 0; box-sizing: border-box; }
body { background-color: #0f172a; color: #e2e8f0; font-family: 'Inter', 'Segoe UI', sans-serif; }
"""
        with open(f"{base_path}/frontend/src/index.css", "w") as f:
            f.write(index_css)
        archivos_generados.append("frontend/src/index.css")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ frontend/src/index.css'})}\n\n"

        # tailwind.config.js fijo
        tailwind_config = """/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
"""
        with open(f"{base_path}/frontend/tailwind.config.js", "w") as f:
            f.write(tailwind_config)
        archivos_generados.append("frontend/tailwind.config.js")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ frontend/tailwind.config.js'})}\n\n"

        # postcss.config.js fijo
        postcss_config = """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
"""
        # _redirects fijo para Render SPA
        os.makedirs(f"{base_path}/frontend/public", exist_ok=True)
        redirects = "/*  /index.html  200\n"
        with open(f"{base_path}/frontend/public/_redirects", "w") as f:
            f.write(redirects)
        archivos_generados.append("frontend/public/_redirects")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ frontend/public/_redirects'})}\n\n"

        # tsconfig.json fijo
        tsconfig = """{
            "compilerOptions": {
                "target": "ES2020",
                "useDefineForClassFields": true,
                "lib": ["ES2020", "DOM", "DOM.Iterable"],
                "module": "ESNext",
                "skipLibCheck": true,
                "moduleResolution": "bundler",
                "allowImportingTsExtensions": true,
                "resolveJsonModule": true,
                "isolatedModules": true,
                "noEmit": true,
                "jsx": "react-jsx",
                "strict": true,
                "types": ["vite/client"]
            },
            "include": ["src"],
            "exclude": ["src/__tests__", "src/**/*.test.tsx", "src/**/*.test.ts", "node_modules"],
            "references": [{ "path": "./tsconfig.node.json" }]
        }
        """
        with open(f"{base_path}/frontend/tsconfig.json", "w") as f:
            f.write(tsconfig)
        archivos_generados.append("frontend/tsconfig.json")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ frontend/tsconfig.json'})}\n\n"

        # tsconfig.node.json fijo
        tsconfig_node = """{
            "compilerOptions": {
                "composite": true,
                "skipLibCheck": true,
                "module": "ESNext",
                "moduleResolution": "bundler",
                "allowSyntheticDefaultImports": true
            },
            "include": ["vite.config.ts"]
        }
        """
        with open(f"{base_path}/frontend/tsconfig.node.json", "w") as f:
            f.write(tsconfig_node)
        archivos_generados.append("frontend/tsconfig.node.json")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ frontend/tsconfig.node.json'})}\n\n"


        # Dockerfiles solo en proyecto nuevo
        if not es_modificacion:
            dockerfile_back = "FROM node:18-alpine\nWORKDIR /app\nCOPY package*.json ./\nRUN npm install --production\nCOPY . .\nEXPOSE 5000\nCMD [\"node\", \"server.js\"]\n"
            with open(f"{base_path}/backend/Dockerfile", "w") as f:
                f.write(dockerfile_back)
            archivos_generados.append("backend/Dockerfile")
            yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ backend/Dockerfile'})}\n\n"

            dockerfile_front = "FROM node:18-alpine AS build\nWORKDIR /app\nCOPY package*.json ./\nRUN npm install\nCOPY . .\nRUN npm run build\n\nFROM nginx:alpine\nCOPY --from=build /app/dist /usr/share/nginx/html\nEXPOSE 80\nCMD [\"nginx\", \"-g\", \"daemon off;\"]\n"
            with open(f"{base_path}/frontend/Dockerfile", "w") as f:
                f.write(dockerfile_front)
            archivos_generados.append("frontend/Dockerfile")
            yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ frontend/Dockerfile'})}\n\n"

            yield f"data: {json.dumps({'tipo': 'archivo', 'texto': '⚙️ Generando docker-compose.yml...'})}\n\n"
            compose = llm.invoke(f"Generá SOLO docker-compose.yml para stack MERN. Servicios: backend puerto 5000, frontend puerto 80, mongodb puerto 27017. Proyecto: {nombre}. SOLO YAML.").content
            with open(f"{base_path}/docker-compose.yml", "w") as f:
                f.write(compose)
            archivos_generados.append("docker-compose.yml")
            yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ docker-compose.yml'})}\n\n"

        # Mensaje resumen
        accion = "modificado" if es_modificacion else "generado"
        resumen = f"{'🔄' if es_modificacion else '🚀'} Proyecto '{nombre}' {accion} exitosamente!"
        yield f"data: {json.dumps({'tipo': 'finalizado', 'proyecto': nombre, 'archivos': archivos_generados, 'resumen': resumen})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )

@app.post("/analizar")
def analizar_repo(data: AnalisisRepo):
    resultado = agente.invoke({
        "instrucciones": "",
        "nombre_proyecto": "",
        "archivos_generados": [],
        "mensaje_final": "",
        "modo": "analizar",
        "repo_url": data.repo_url,
        "analisis": None,
    })
    return {
        "proyecto": resultado["nombre_proyecto"],
        "archivos": resultado["archivos_generados"],
        "mensaje": resultado["mensaje_final"]
    }

@app.get("/proyectos")
def listar_proyectos():
    ruta_base = "./proyectos"
    if not os.path.exists(ruta_base):
        return {"proyectos": []}
    proyectos = []
    for nombre in os.listdir(ruta_base):
        ruta = os.path.join(ruta_base, nombre)
        if os.path.isdir(ruta):
            archivos = []
            for root, dirs, files in os.walk(ruta):
                dirs[:] = [d for d in dirs if d != "node_modules"]
                for file in files:
                    filepath = os.path.join(root, file)
                    arcname = os.path.relpath(filepath, ruta)
                    archivos.append(arcname.replace("\\", "/"))
            proyectos.append({
                "nombre": nombre,
                "archivos": archivos,
                "creado": os.path.getctime(ruta),
            })
    proyectos.sort(key=lambda x: x["creado"], reverse=True)
    return {"proyectos": proyectos}

@app.delete("/proyectos/{nombre_proyecto}")
def eliminar_proyecto(nombre_proyecto: str):
    ruta = f"./proyectos/{nombre_proyecto}"
    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    shutil.rmtree(ruta)
    return {"mensaje": f"Proyecto '{nombre_proyecto}' eliminado"}

@app.get("/archivo/{nombre_proyecto}/{ruta_archivo:path}")
def leer_archivo(nombre_proyecto: str, ruta_archivo: str):
    ruta = f"./proyectos/{nombre_proyecto}/{ruta_archivo}"
    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    try:
        with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
            contenido = f.read()
        return {"contenido": contenido}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/archivo/{nombre_proyecto}/{ruta_archivo:path}")
def guardar_archivo(nombre_proyecto: str, ruta_archivo: str, data: GuardarArchivo):
    ruta = f"./proyectos/{nombre_proyecto}/{ruta_archivo}"
    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(data.contenido)
        return {"mensaje": "Archivo guardado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/descargar/{nombre_proyecto}")
def descargar_proyecto(nombre_proyecto: str):
    ruta = f"./proyectos/{nombre_proyecto}"
    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(ruta):
            dirs[:] = [d for d in dirs if d != "node_modules"]
            for file in files:
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, ruta)
                zip_file.write(filepath, arcname)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={nombre_proyecto}.zip"}
    )

@app.post("/generar/tests")
async def generar_tests(data: GenerarTests):
    async def event_stream():
        base_path = f"./proyectos/{data.nombre_proyecto}"

        if not os.path.exists(base_path):
            yield f"data: {json.dumps({'tipo': 'error', 'texto': '❌ Proyecto no encontrado'})}\n\n"
            return

        os.makedirs(f"{base_path}/backend/tests", exist_ok=True)
        os.makedirs(f"{base_path}/frontend/src/__tests__", exist_ok=True)

        archivos_generados = []

        # jest.config.js
        yield f"data: {json.dumps({'tipo': 'archivo', 'texto': '⚙️ Generando jest.config.js...'})}\n\n"
        jest_config = """module.exports = {
  testEnvironment: 'node',
  testMatch: ['**/tests/**/*.test.js'],
  collectCoverageFrom: [
    'controllers/**/*.js',
    'routes/**/*.js',
    'models/**/*.js',
  ],
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 70,
      lines: 70,
    },
  },
};
"""
        with open(f"{base_path}/backend/jest.config.js", "w") as f:
            f.write(jest_config)
        archivos_generados.append("backend/jest.config.js")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ backend/jest.config.js'})}\n\n"

        # tests de auth
        yield f"data: {json.dumps({'tipo': 'archivo', 'texto': '⚙️ Generando tests/auth.test.js...'})}\n\n"
        auth_test = llm.invoke(f"""
        Generá SOLO el código de tests con Jest y Supertest para autenticación Express.
        Proyecto: {data.instrucciones}
        Incluí tests para: POST /api/auth/register, POST /api/auth/login, token inválido.
        Usá describe/it/expect. Mockeá MongoDB con jest.mock.
        SOLO código JavaScript, sin explicaciones ni markdown.
        """).content
        with open(f"{base_path}/backend/tests/auth.test.js", "w") as f:
            f.write(auth_test)
        archivos_generados.append("backend/tests/auth.test.js")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ backend/tests/auth.test.js'})}\n\n"

        # tests de API
        yield f"data: {json.dumps({'tipo': 'archivo', 'texto': '⚙️ Generando tests/api.test.js...'})}\n\n"
        api_test = llm.invoke(f"""
        Generá SOLO el código de tests con Jest y Supertest para endpoints CRUD.
        Proyecto: {data.instrucciones}
        Incluí tests para: GET, POST, PUT, DELETE con autenticación JWT.
        Usá describe/it/expect. Incluí beforeAll/afterAll para setup.
        SOLO código JavaScript, sin explicaciones ni markdown.
        """).content
        with open(f"{base_path}/backend/tests/api.test.js", "w") as f:
            f.write(api_test)
        archivos_generados.append("backend/tests/api.test.js")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ backend/tests/api.test.js'})}\n\n"

        # tests de modelos
        yield f"data: {json.dumps({'tipo': 'archivo', 'texto': '⚙️ Generando tests/model.test.js...'})}\n\n"
        model_test = llm.invoke(f"""
        Generá SOLO el código de tests con Jest para modelos Mongoose.
        Proyecto: {data.instrucciones}
        Incluí tests para: validación de campos requeridos, campos únicos, métodos del modelo.
        Usá mongodb-memory-server para tests en memoria.
        SOLO código JavaScript, sin explicaciones ni markdown.
        """).content
        with open(f"{base_path}/backend/tests/model.test.js", "w") as f:
            f.write(model_test)
        archivos_generados.append("backend/tests/model.test.js")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ backend/tests/model.test.js'})}\n\n"

        # tests frontend
        yield f"data: {json.dumps({'tipo': 'archivo', 'texto': '⚙️ Generando frontend tests...'})}\n\n"
        frontend_test = llm.invoke(f"""
        Generá SOLO el código de tests con Vitest y React Testing Library para App.tsx.
        Proyecto: {data.instrucciones}
        Incluí tests para: renderizado inicial, interacciones de usuario, llamadas a la API mockeadas.
        Usá describe/it/expect, vi.mock para fetch.
        SOLO código TypeScript, sin explicaciones ni markdown.
        """).content
        with open(f"{base_path}/frontend/src/__tests__/App.test.tsx", "w") as f:
            f.write(frontend_test)
        archivos_generados.append("frontend/src/__tests__/App.test.tsx")
        yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': '✅ frontend/src/__tests__/App.test.tsx'})}\n\n"

        yield f"data: {json.dumps({'tipo': 'finalizado', 'proyecto': data.nombre_proyecto, 'archivos': archivos_generados})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )

@app.post("/auth/register")
def register(data: RegisterData):
    # Verificar si ya existe
    if users_collection.find_one({"email": data.email}):
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    # Crear usuario
    usuario = {
        "nombre": data.nombre,
        "email": data.email,
        "password": hash_password(data.password),
        "rol": "user",
        "plan": "free",
        "proyectos_count": 0,
        "creado": datetime.utcnow(),
    }
    resultado = users_collection.insert_one(usuario)
    user_id = str(resultado.inserted_id)

    token = crear_token({"sub": user_id, "email": data.email, "rol": "user"})
    return {
        "token": token,
        "usuario": {
            "id": user_id,
            "nombre": data.nombre,
            "email": data.email,
            "rol": "user",
            "plan": "free",
        }
    }

@app.post("/auth/login")
def login(data: LoginData):
    usuario = users_collection.find_one({"email": data.email})
    if not usuario:
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    if not verify_password(data.password, usuario["password"]):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    user_id = str(usuario["_id"])
    token = crear_token({
        "sub": user_id,
        "email": usuario["email"],
        "rol": usuario.get("rol", "user")
    })

    return {
        "token": token,
        "usuario": {
            "id": user_id,
            "nombre": usuario["nombre"],
            "email": usuario["email"],
            "rol": usuario.get("rol", "user"),
            "plan": usuario.get("plan", "free"),
        }
    }

@app.get("/auth/me")
def get_me(authorization: str = None):
    from fastapi import Header
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    token = authorization.replace("Bearer ", "")
    payload = verificar_token(token)
    user_id = payload.get("sub")
    usuario = users_collection.find_one({"_id": ObjectId(user_id)})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {
        "id": str(usuario["_id"]),
        "nombre": usuario["nombre"],
        "email": usuario["email"],
        "rol": usuario.get("rol", "user"),
        "plan": usuario.get("plan", "free"),
    }

@app.post("/exportar/github")
async def exportar_github(data: ExportGithub):
    async def event_stream():
        base_path = f"./proyectos/{data.nombre_proyecto}"

        if not os.path.exists(base_path):
            yield f"data: {json.dumps({'tipo': 'error', 'texto': '❌ Proyecto no encontrado'})}\n\n"
            return

        github_token = os.getenv("GITHUB_TOKEN")
        github_username = os.getenv("GITHUB_USERNAME")

        if not github_token or not github_username:
            yield f"data: {json.dumps({'tipo': 'error', 'texto': '❌ GitHub token no configurado'})}\n\n"
            return

        import base64
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }

        # Paso 1: Crear repo en GitHub
        yield f"data: {json.dumps({'tipo': 'estado', 'texto': '🐙 Creando repositorio en GitHub...'})}\n\n"

        repo_data = json.dumps({
            "name": data.nombre_proyecto,
            "description": f"Proyecto MERN generado por MERN Dev Agent",
            "private": False,
            "auto_init": False,
        }).encode("utf-8")

        try:
            import urllib.request
            req = urllib.request.Request(
                "https://api.github.com/user/repos",
                data=repo_data,
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req) as res:
                repo_info = json.loads(res.read().decode())
                repo_url = repo_info["html_url"]
                yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'✅ Repo creado: {repo_url}'})}\n\n"
        except urllib.error.HTTPError as e:
            error_body = json.loads(e.read().decode())
            if "already exists" in str(error_body):
                repo_url = f"https://github.com/{github_username}/{data.nombre_proyecto}"
                yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'📁 Repo ya existe: {repo_url}'})}\n\n"
            else:
                yield f"data: {json.dumps({'tipo': 'error', 'texto': f'❌ Error creando repo: {error_body}'})}\n\n"
                return

        # Paso 2: Subir archivos
        yield f"data: {json.dumps({'tipo': 'estado', 'texto': '📤 Subiendo archivos...'})}\n\n"

        archivos_subidos = []
        for root, dirs, files in os.walk(base_path):
            dirs[:] = [d for d in dirs if d not in ["node_modules", ".git"]]
            for file in files:
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, base_path).replace("\\", "/")

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        contenido = f.read()

                    contenido_b64 = base64.b64encode(
                        contenido.encode("utf-8")
                    ).decode("utf-8")

                    file_data = json.dumps({
                        "message": f"Add {arcname}",
                        "content": contenido_b64,
                    }).encode("utf-8")

                    req = urllib.request.Request(
                        f"https://api.github.com/repos/{github_username}/{data.nombre_proyecto}/contents/{arcname}",
                        data=file_data,
                        headers=headers,
                        method="PUT"
                    )
                    with urllib.request.urlopen(req) as res:
                        res.read()

                    archivos_subidos.append(arcname)
                    yield f"data: {json.dumps({'tipo': 'archivo_ok', 'texto': f'✅ {arcname}'})}\n\n"

                except Exception as e:
                    yield f"data: {json.dumps({'tipo': 'archivo', 'texto': f'⚠️ Skip {arcname}: {str(e)[:50]}'})}\n\n"

        # Finalizar
        yield f"data: {json.dumps({'tipo': 'finalizado', 'repo_url': repo_url, 'archivos': archivos_subidos})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )

async def subir_archivo_github(github_token: str, github_username: str, repo: str, ruta: str, contenido: str, client: httpx.AsyncClient):
    import base64
    contenido_b64 = base64.b64encode(contenido.encode("utf-8")).decode("utf-8")

    # Verificar si el archivo ya existe (necesitamos el sha para actualizarlo)
    sha = None
    check_response = await client.get(
        f"https://api.github.com/repos/{github_username}/{repo}/contents/{ruta}",
        headers={
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
    )
    if check_response.status_code == 200:
        sha = check_response.json().get("sha")

    payload = {
        "message": f"Add {ruta} via deploy",
        "content": contenido_b64,
    }
    if sha:
        payload["sha"] = sha

    response = await client.put(
        f"https://api.github.com/repos/{github_username}/{repo}/contents/{ruta}",
        headers={
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
        json=payload
    )
    return response.status_code in [200, 201]

@app.post("/deploy/render")
async def deploy_render(data: DeployRender):
    async def event_stream():
        render_api_key = os.getenv("RENDER_API_KEY")

        if not render_api_key:
            yield f"data: {json.dumps({'tipo': 'error', 'texto': '❌ Render API Key no configurada'})}\n\n"
            return

        headers = {
            "Authorization": f"Bearer {render_api_key}",
            "Content-Type": "application/json",
        }

        # Esperar a que GitHub propague todos los commits del export antes de clonar
        yield f"data: {json.dumps({'tipo': 'estado', 'texto': '⏳ Esperando sincronización de GitHub...'})}\n\n"
        await asyncio.sleep(8)

        # Obtener owner ID real
        yield f"data: {json.dumps({'tipo': 'estado', 'texto': '🔍 Obteniendo owner ID de Render...'})}\n\n"

        try:
            req = urllib.request.Request(
                "https://api.render.com/v1/owners?limit=1",
                headers=headers,
                method="GET"
            )
            with urllib.request.urlopen(req) as res:
                owners_info = json.loads(res.read().decode())
                owner_id = owners_info[0]["owner"]["id"]
                yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'✅ Owner ID obtenido'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'tipo': 'error', 'texto': f'❌ Error obteniendo owner ID: {str(e)}'})}\n\n"
            return

        # Nombre único con timestamp
        import time
        sufijo = str(int(time.time()))[-4:]
        backend_name = f"{data.nombre_proyecto}-back-{sufijo}"
        frontend_name = f"{data.nombre_proyecto}-front-{sufijo}"
        backend_url = f"https://{backend_name}.onrender.com"
        frontend_url = f"https://{frontend_name}.onrender.com"

        # Paso 1: Deploy backend
        yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'🚀 Creando servicio backend: {backend_name}...'})}\n\n"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.render.com/v1/services",
                    headers={
                        "Authorization": f"Bearer {render_api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json={
                        "type": "web_service",
                        "name": backend_name,
                        "ownerId": owner_id,
                        "repo": data.repo_url,
                        "autoDeploy": "yes",
                        "branch": "main",
                        "serviceDetails": {
                            "env": "node",
                            "plan": "free",
                            "region": "oregon",
                            "envSpecificDetails": {
                                "buildCommand": "cd backend && npm install",
                                "startCommand": "cd backend && node server.js",
                            },
                        }
                    }
                )

                if response.status_code in [200, 201]:
                    service_info = response.json()
                    service_id = service_info["service"]["id"]
                    yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'✅ Backend creado: {backend_url}'})}\n\n"

                    # Paso 1b: asignar variables de entorno por separado
                    yield f"data: {json.dumps({'tipo': 'estado', 'texto': '🔐 Configurando variables de entorno...'})}\n\n"

                    env_response = await client.put(
                        f"https://api.render.com/v1/services/{service_id}/env-vars",
                        headers={
                            "Authorization": f"Bearer {render_api_key}",
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                        },
                        json=[
                            {"key": "PORT", "value": "5000"},
                            {"key": "NODE_ENV", "value": "production"},
                            {"key": "MONGO_URI", "value": os.getenv("MONGO_URI", "")},
                            {"key": "JWT_SECRET", "value": os.getenv("JWT_SECRET", "")},
                        ]
                    )

                    if env_response.status_code in [200, 201]:
                        yield f"data: {json.dumps({'tipo': 'estado', 'texto': '✅ Variables de entorno configuradas'})}\n\n"
                    else:
                        yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'⚠️ Env vars: {env_response.text[:150]}'})}\n\n"
                else:
                    yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'⚠️ Backend: {response.text[:150]}'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'⚠️ Backend error: {str(e)[:100]}'})}\n\n"

        # Paso 1c: subir .env.production al repo con la URL real del backend
        yield f"data: {json.dumps({'tipo': 'estado', 'texto': '📝 Configurando URL del backend en el frontend...'})}\n\n"

        github_token = os.getenv("GITHUB_TOKEN")
        github_username = os.getenv("GITHUB_USERNAME")
        repo_nombre = data.repo_url.rstrip("/").split("/")[-1]

        env_production = f"VITE_API_URL={backend_url}\n"

        async with httpx.AsyncClient() as gh_client:
            subido = await subir_archivo_github(
                github_token, github_username, repo_nombre,
                "frontend/.env.production", env_production, gh_client
            )

        if subido:
            yield f"data: {json.dumps({'tipo': 'estado', 'texto': '✅ .env.production configurado en el repo'})}\n\n"
        else:
            yield f"data: {json.dumps({'tipo': 'estado', 'texto': '⚠️ No se pudo subir .env.production'})}\n\n"



        # Paso 2: Deploy frontend
        yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'🌐 Creando servicio frontend: {frontend_name}...'})}\n\n"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.render.com/v1/services",
                    headers={
                        "Authorization": f"Bearer {render_api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json={
                        "type": "static_site",
                        "name": frontend_name,
                        "ownerId": owner_id,
                        "repo": data.repo_url,
                        "autoDeploy": "yes",
                        "branch": "main",
                        "serviceDetails": {
                            "buildCommand": "cd frontend && npm install && npm run build",
                            "publishPath": "frontend/dist",
                        }
                    }
                )
                if response.status_code in [200, 201]:
                    service_info = response.json()
                    service_id = service_info["service"]["id"]
                    yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'✅ Frontend creado: {frontend_url}'})}\n\n"

                    env_response = await client.put(
                        f"https://api.render.com/v1/services/{service_id}/env-vars",
                        headers={
                            "Authorization": f"Bearer {render_api_key}",
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                        },
                        json=[
                            {"key": "VITE_API_URL", "value": backend_url},
                        ]
                    )
                    if env_response.status_code in [200, 201]:
                        yield f"data: {json.dumps({'tipo': 'estado', 'texto': '✅ VITE_API_URL configurada'})}\n\n"
                    else:
                        yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'⚠️ Env var frontend: {env_response.text[:150]}'})}\n\n"
                else:
                    yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'⚠️ Frontend: {response.text[:150]}'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'tipo': 'estado', 'texto': f'⚠️ Frontend error: {str(e)[:100]}'})}\n\n"

        # Finalizar
        yield f"data: {json.dumps({'tipo': 'finalizado', 'backend_url': backend_url, 'frontend_url': frontend_url})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )