import os
import git
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional

load_dotenv()

class AgentState(TypedDict):
    instrucciones: str
    nombre_proyecto: str
    archivos_generados: list[str]
    mensaje_final: str
    modo: str
    repo_url: Optional[str]
    analisis: Optional[str]

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    groq_api_key=os.getenv("GROQ_API_KEY")
)

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def escribir_archivo(path: str, contenido: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)

def generar(prompt: str) -> str:
    return llm.invoke(prompt).content

# ─────────────────────────────────────────
# MODO NUEVO PROYECTO
# ─────────────────────────────────────────

def analizar_instrucciones(state: AgentState) -> AgentState:
    respuesta = generar(f"""
    Eres un arquitecto de software MERN experto.
    El cliente quiere: {state['instrucciones']}
    Respondé SOLO con el nombre del proyecto en una palabra, en minúsculas.
    Ejemplo: ecommerce, taskmanager, blogapp
    """)
    state["nombre_proyecto"] = respuesta.strip()
    return state

def generar_codigo(state: AgentState) -> AgentState:
    proyecto = state["nombre_proyecto"]
    inst = state["instrucciones"]
    base = f"./proyectos/{proyecto}"
    archivos = []

    # Estructura de carpetas
    for carpeta in [
        f"{base}/backend/models",
        f"{base}/backend/routes",
        f"{base}/backend/controllers",
        f"{base}/backend/middleware",
        f"{base}/frontend/src/components",
        f"{base}/frontend/src/pages",
        f"{base}/frontend/src/store",
    ]:
        os.makedirs(carpeta, exist_ok=True)

    # ── server.js ──
    code = generar(f"""
    Generá SOLO el código de server.js para Express.js.
    Proyecto: {inst}
    Incluí: helmet, cors configurado, express-rate-limit, rutas, conexión MongoDB, puerto desde .env.
    SOLO código JavaScript, sin explicaciones ni markdown.
    """)
    escribir_archivo(f"{base}/backend/server.js", code)
    archivos.append("backend/server.js")

    # ── middleware/auth.js ──
    code = generar(f"""
    Generá SOLO el código de middleware/auth.js para Express.js.
    Incluí: verificación JWT con jsonwebtoken, manejo de errores 401/403.
    SOLO código JavaScript, sin explicaciones ni markdown.
    """)
    escribir_archivo(f"{base}/backend/middleware/auth.js", code)
    archivos.append("backend/middleware/auth.js")

    # ── middleware/validate.js ──
    code = generar(f"""
    Generá SOLO el código de middleware/validate.js para Express.js.
    Incluí: validación con express-validator, manejo de errores de validación.
    SOLO código JavaScript, sin explicaciones ni markdown.
    """)
    escribir_archivo(f"{base}/backend/middleware/validate.js", code)
    archivos.append("backend/middleware/validate.js")

    # ── models/User.js ──
    code = generar(f"""
    Generá SOLO el código de models/User.js con Mongoose.
    Incluí: campos email, password (hasheado con bcryptjs), rol, timestamps.
    Incluí método comparePassword y hook pre-save para hashear.
    SOLO código JavaScript, sin explicaciones ni markdown.
    """)
    escribir_archivo(f"{base}/backend/models/User.js", code)
    archivos.append("backend/models/User.js")

    # ── models/Model.js ──
    code = generar(f"""
    Generá SOLO el código del modelo Mongoose principal para: {inst}
    SOLO código JavaScript, sin explicaciones ni markdown.
    """)
    escribir_archivo(f"{base}/backend/models/Model.js", code)
    archivos.append("backend/models/Model.js")

    # ── controllers/authController.js ──
    code = generar(f"""
    Generá SOLO el código de controllers/authController.js para Express.js.
    Incluí: register (hashear password con bcryptjs), login (generar JWT), logout.
    Usá el modelo User de Mongoose.
    SOLO código JavaScript, sin explicaciones ni markdown.
    """)
    escribir_archivo(f"{base}/backend/controllers/authController.js", code)
    archivos.append("backend/controllers/authController.js")

    # ── controllers/controller.js ──
    code = generar(f"""
    Generá SOLO el código del controlador principal para: {inst}
    Incluí funciones CRUD completas usando Mongoose.
    SOLO código JavaScript, sin explicaciones ni markdown.
    """)
    escribir_archivo(f"{base}/backend/controllers/controller.js", code)
    archivos.append("backend/controllers/controller.js")

    # ── routes/authRoutes.js ──
    code = generar(f"""
    Generá SOLO el código de routes/authRoutes.js para Express.js.
    Incluí: POST /register, POST /login, POST /logout con express-validator.
    SOLO código JavaScript, sin explicaciones ni markdown.
    """)
    escribir_archivo(f"{base}/backend/routes/authRoutes.js", code)
    archivos.append("backend/routes/authRoutes.js")

    # ── routes/routes.js ──
    code = generar(f"""
    Generá SOLO el código de rutas Express protegidas con JWT para: {inst}
    Incluí middleware de auth en rutas protegidas. CRUD completo.
    SOLO código JavaScript, sin explicaciones ni markdown.
    """)
    escribir_archivo(f"{base}/backend/routes/routes.js", code)
    archivos.append("backend/routes/routes.js")

    # ── package.json backend ──
    code = generar(f"""
    Generá SOLO el contenido de package.json para backend Express.js.
    Nombre: {proyecto}-backend
    Dependencias: express, mongoose, cors, dotenv, jsonwebtoken, bcryptjs,
    helmet, express-rate-limit, express-validator.
    devDependencies: nodemon.
    Scripts: start, dev.
    SOLO JSON, sin explicaciones ni markdown.
    """)
    escribir_archivo(f"{base}/backend/package.json", code)
    archivos.append("backend/package.json")

    # ── .env.example ──
    code = generar(f"""
    Generá SOLO el contenido de .env.example para: {inst}
    Incluí: MONGO_URI, JWT_SECRET, JWT_EXPIRES_IN, PORT, NODE_ENV, CORS_ORIGIN.
    SOLO el contenido, sin explicaciones ni markdown.
    """)
    escribir_archivo(f"{base}/backend/.env.example", code)
    archivos.append("backend/.env.example")

    # ── Dockerfile backend ──
    dockerfile_back = """FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --production
COPY . .
EXPOSE 5000
CMD ["node", "server.js"]
"""
    escribir_archivo(f"{base}/backend/Dockerfile", dockerfile_back)
    archivos.append("backend/Dockerfile")

    # ── .dockerignore backend ──
    dockerignore = "node_modules\n.env\nnpm-debug.log\n"
    escribir_archivo(f"{base}/backend/.dockerignore", dockerignore)
    archivos.append("backend/.dockerignore")

    # ── App.tsx frontend ──
    code = generar(f"""
    Generá SOLO el código de App.tsx en React con TypeScript para: {inst}
    Usá fetch para conectarte a API REST en puerto 5000.
    Incluí manejo de JWT en localStorage para auth.
    SOLO código TypeScript/React, sin explicaciones ni markdown.
    """)
    escribir_archivo(f"{base}/frontend/src/App.tsx", code)
    archivos.append("frontend/src/App.tsx")

    # ── package.json frontend ──
    code = generar(f"""
    Generá SOLO el contenido de package.json para proyecto React con Vite y TypeScript.
    Nombre: {proyecto}-frontend
    Dependencias: react, react-dom, axios, zustand.
    devDependencies: vite, typescript, @vitejs/plugin-react, tailwindcss.
    Scripts: dev, build, preview.
    SOLO JSON, sin explicaciones ni markdown.
    """)
    escribir_archivo(f"{base}/frontend/package.json", code)
    archivos.append("frontend/package.json")

    # ── Dockerfile frontend ──
    dockerfile_front = """FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
"""
    escribir_archivo(f"{base}/frontend/Dockerfile", dockerfile_front)
    archivos.append("frontend/Dockerfile")

    # ── docker-compose.yml ──
    compose = generar(f"""
    Generá SOLO el contenido de docker-compose.yml para un proyecto MERN.
    Servicios: backend (puerto 5000), frontend (puerto 80), mongodb (puerto 27017).
    Incluí: volúmenes para MongoDB, variables de entorno, depends_on, network.
    Nombre del proyecto: {proyecto}
    SOLO YAML, sin explicaciones ni markdown.
    """)
    escribir_archivo(f"{base}/docker-compose.yml", compose)
    archivos.append("docker-compose.yml")

    # ── README.md ──
    readme = generar(f"""
    Generá SOLO el contenido de un README.md profesional para: {inst}
    Incluí: descripción, stack, requisitos, instalación local, instalación con Docker,
    variables de entorno, endpoints de la API, seguridad implementada.
    SOLO markdown, sin explicaciones adicionales.
    """)
    escribir_archivo(f"{base}/README.md", readme)
    archivos.append("README.md")

    state["archivos_generados"] = archivos
    return state

def finalizar_nuevo(state: AgentState) -> AgentState:
    archivos = "\n".join([f"✅ {a}" for a in state["archivos_generados"]])
    state["mensaje_final"] = f"""
🚀 Proyecto '{state['nombre_proyecto']}' generado exitosamente!

Archivos creados:
{archivos}

Ubicación: ./proyectos/{state['nombre_proyecto']}

🔒 Seguridad incluida:
- JWT Authentication
- Passwords hasheados con bcryptjs
- Helmet.js (headers HTTP seguros)
- Rate limiting (anti fuerza bruta)
- Validación de inputs con express-validator
- CORS configurado correctamente

🐳 Docker incluido:
- Dockerfile backend y frontend
- docker-compose.yml (un comando levanta todo)
    """
    return state

# ─────────────────────────────────────────
# MODO ANÁLISIS DE REPO GITHUB
# ─────────────────────────────────────────

def clonar_repo(state: AgentState) -> AgentState:
    repo_url = state["repo_url"]
    nombre = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    state["nombre_proyecto"] = nombre
    destino = f"./repos/{nombre}"

    if os.path.exists(destino):
        state["analisis"] = f"📁 Repo ya clonado en {destino}"
    else:
        os.makedirs("./repos", exist_ok=True)
        git.Repo.clone_from(repo_url, destino)
        state["analisis"] = f"✅ Repo clonado en {destino}"
    return state

def analizar_repo(state: AgentState) -> AgentState:
    nombre = state["nombre_proyecto"]
    repo_path = f"./repos/{nombre}"
    contenido = ""
    extensiones = [".js", ".jsx", ".ts", ".tsx", ".json", ".py"]
    archivos_leidos = 0

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", "venv", "__pycache__", "dist"]]
        for file in files:
            if any(file.endswith(ext) for ext in extensiones) and archivos_leidos < 15:
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        codigo = f.read()[:1500]
                        ruta = filepath.replace(repo_path, "")
                        contenido += f"\n\n### {ruta}\n{codigo}"
                        archivos_leidos += 1
                except:
                    pass

    analisis = generar(f"""
    Eres un senior developer MERN experto en code review y ciberseguridad.
    Analizá el siguiente código:

    {contenido}

    Respondé con:
    1. 📋 RESUMEN DEL PROYECTO (qué hace, stack detectado)
    2. ✅ PUNTOS FUERTES
    3. ⚠️ MEJORAS SUGERIDAS (por prioridad)
    4. 🔒 SEGURIDAD (vulnerabilidades OWASP detectadas)
    5. 🐳 DOCKER (si no tiene, sugerí cómo dockerizarlo)
    6. 📈 PRÓXIMOS PASOS

    Sé específico y técnico. Mencioná archivos cuando sea relevante.
    """)

    state["analisis"] = analisis
    state["archivos_generados"] = [f"Analizados: {archivos_leidos} archivos"]
    return state

def finalizar_analisis(state: AgentState) -> AgentState:
    state["mensaje_final"] = f"""
🔍 Análisis del repo '{state['nombre_proyecto']}' completado!

{state['analisis']}
    """
    return state

# ─────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────

def router(state: AgentState) -> str:
    if state.get("modo") == "analizar":
        return "clonar"
    return "analizar_instrucciones"

# ─────────────────────────────────────────
# GRAFO
# ─────────────────────────────────────────

def construir_agente():
    grafo = StateGraph(AgentState)

    grafo.add_node("analizar_instrucciones", analizar_instrucciones)
    grafo.add_node("generar", generar_codigo)
    grafo.add_node("finalizar_nuevo", finalizar_nuevo)
    grafo.add_node("clonar", clonar_repo)
    grafo.add_node("analizar_repo", analizar_repo)
    grafo.add_node("finalizar_analisis", finalizar_analisis)

    grafo.set_conditional_entry_point(
        router,
        {
            "analizar_instrucciones": "analizar_instrucciones",
            "clonar": "clonar",
        }
    )

    grafo.add_edge("analizar_instrucciones", "generar")
    grafo.add_edge("generar", "finalizar_nuevo")
    grafo.add_edge("finalizar_nuevo", END)

    grafo.add_edge("clonar", "analizar_repo")
    grafo.add_edge("analizar_repo", "finalizar_analisis")
    grafo.add_edge("finalizar_analisis", END)

    return grafo.compile()

agente = construir_agente()