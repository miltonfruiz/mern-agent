import { useState } from "react";
import { motion } from "framer-motion";
import {
  RiCodeSSlashLine,
  RiMailLine,
  RiLockPasswordLine,
  RiLoader4Line,
  RiUserLine,
} from "react-icons/ri";
import { useAuthStore } from "../store/useAuthStore";

const API = "http://127.0.0.1:8000";

interface RegisterProps {
  onIrALogin: () => void;
}

export default function Register({ onIrALogin }: RegisterProps) {
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  const { setUsuario } = useAuthStore();

  const handleRegister = async () => {
    if (!nombre.trim() || !email.trim() || !password.trim()) {
      setError("Completá todos los campos");
      return;
    }
    if (password.length < 6) {
      setError("La contraseña debe tener al menos 6 caracteres");
      return;
    }
    setCargando(true);
    setError("");
    try {
      const res = await fetch(`${API}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre, email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Error al registrarse");
        return;
      }
      setUsuario(data.usuario, data.token);
    } catch {
      setError("Error al conectar con el servidor");
    } finally {
      setCargando(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleRegister();
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md"
      >
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-violet-600/20 border border-violet-500/30 flex items-center justify-center mb-4">
            <RiCodeSSlashLine className="text-violet-400 text-3xl" />
          </div>
          <h1 className="text-2xl font-bold text-white">MERN Dev Agent</h1>
          <p className="text-sm text-slate-500 mt-1">Creá tu cuenta gratis</p>
        </div>

        {/* Card */}
        <div className="bg-slate-900/80 border border-slate-700/50 rounded-2xl p-8">
          <h2 className="text-lg font-bold text-white mb-6">Crear cuenta</h2>

          <div className="flex flex-col gap-4">
            {/* Nombre */}
            <div className="flex items-center gap-3 bg-slate-800/60 border border-slate-700/50 rounded-xl px-4 py-3 focus-within:border-violet-500/50 transition-all">
              <RiUserLine className="text-slate-500 flex-shrink-0" />
              <input
                className="flex-1 bg-transparent text-sm text-slate-200 outline-none placeholder-slate-600"
                type="text"
                placeholder="Tu nombre"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                onKeyDown={handleKeyDown}
              />
            </div>

            {/* Email */}
            <div className="flex items-center gap-3 bg-slate-800/60 border border-slate-700/50 rounded-xl px-4 py-3 focus-within:border-violet-500/50 transition-all">
              <RiMailLine className="text-slate-500 flex-shrink-0" />
              <input
                className="flex-1 bg-transparent text-sm text-slate-200 outline-none placeholder-slate-600"
                type="email"
                placeholder="tu@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyDown={handleKeyDown}
              />
            </div>

            {/* Password */}
            <div className="flex items-center gap-3 bg-slate-800/60 border border-slate-700/50 rounded-xl px-4 py-3 focus-within:border-violet-500/50 transition-all">
              <RiLockPasswordLine className="text-slate-500 flex-shrink-0" />
              <input
                className="flex-1 bg-transparent text-sm text-slate-200 outline-none placeholder-slate-600"
                type="password"
                placeholder="Mínimo 6 caracteres"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={handleKeyDown}
              />
            </div>

            {/* Error */}
            {error && (
              <p className="text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
                ❌ {error}
              </p>
            )}

            {/* Plan info */}
            <div className="bg-violet-600/10 border border-violet-500/20 rounded-xl px-4 py-3">
              <p className="text-xs text-violet-300 font-medium">
                ✨ Plan Free incluye:
              </p>
              <ul className="text-xs text-slate-400 mt-1 space-y-0.5">
                <li>• 3 proyectos MERN completos</li>
                <li>• Análisis de repos GitHub</li>
                <li>• Descarga ZIP + Docker incluido</li>
              </ul>
            </div>

            {/* Botón */}
            <button
              onClick={handleRegister}
              disabled={cargando}
              className={`flex items-center justify-center gap-2 w-full py-3 rounded-xl text-sm font-bold transition-all cursor-pointer ${
                cargando
                  ? "bg-slate-700 text-slate-500 cursor-not-allowed"
                  : "bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-500/20"
              }`}
            >
              {cargando ? <RiLoader4Line className="animate-spin" /> : null}
              {cargando ? "Creando cuenta..." : "Crear cuenta gratis"}
            </button>
          </div>

          {/* Login */}
          <p className="text-xs text-slate-500 text-center mt-6">
            ¿Ya tenés cuenta?{" "}
            <button
              onClick={onIrALogin}
              className="text-violet-400 hover:text-violet-300 cursor-pointer transition-colors"
            >
              Iniciá sesión
            </button>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
