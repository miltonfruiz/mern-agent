import { useRef, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  RiRobot2Line,
  RiUser3Line,
  RiSendPlaneFill,
  RiGithubFill,
  RiSparklingFill,
  RiSearchLine,
  RiDownload2Line,
  RiCodeSSlashLine,
  RiDeleteBin6Line,
  RiArrowDownSLine,
  RiSettings4Line,
  RiGlobalLine,
  RiQuestionLine,
  RiVipCrownLine,
  RiLogoutBoxLine,
} from "react-icons/ri";
import { useAgentStore, Modo } from "./store/useAgentStore";
import FileViewer from "./components/FileViewer";
import ProjectHistory from "./components/ProjectHistory";
import TestGenerator from "./components/TestGenerator";
import { useAuthStore } from "./store/useAuthStore";
import GithubExport from "./components/GithubExport";
import DeployRender from "./components/DeployRender";

const API = "http://127.0.0.1:8000";

interface Proyecto {
  nombre: string;
  archivos: string[];
  creado: number;
}

export default function App() {
  const {
    modo,
    setModo,
    mensajes,
    agregarMensaje,
    contexto,
    agregarContexto,
    cargando,
    setCargando,
    instrucciones,
    setInstrucciones,
    repoUrl,
    setRepoUrl,
    proyectoActivo,
    setProyectoActivo,
    limpiarInput,
    limpiarConversacion,
  } = useAgentStore();

  const { usuario, cerrarSesion } = useAuthStore();
  const [menuPerfil, setMenuPerfil] = useState(false);
  const chatRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [mensajes]);

  const enviarStream = async () => {
    if (!instrucciones.trim()) return;

    const textoUsuario = instrucciones;
    agregarMensaje({ rol: "usuario", texto: textoUsuario });
    agregarContexto({ rol: "user", contenido: textoUsuario });
    limpiarInput();
    setCargando(true);

    agregarMensaje({
      rol: "agente",
      texto: "",
      archivos: [],
      proyecto: "",
      streaming: true,
    });

    try {
      const res = await fetch(`${API}/generar/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instrucciones: textoUsuario,
          contexto,
          proyecto_activo: proyectoActivo,
        }),
      });

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let resumenFinal = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n").filter((l) => l.startsWith("data: "));

        for (const line of lines) {
          const data = JSON.parse(line.replace("data: ", ""));

          if (["estado", "archivo", "archivo_ok"].includes(data.tipo)) {
            useAgentStore.setState((state) => {
              const msgs = [...state.mensajes];
              const last = { ...msgs[msgs.length - 1] };
              last.texto = last.texto + "\n" + data.texto;
              msgs[msgs.length - 1] = last;
              return { mensajes: msgs };
            });
          }

          if (data.tipo === "finalizado") {
            resumenFinal = data.resumen;
            setProyectoActivo(data.proyecto);
            useAgentStore.setState((state) => {
              const msgs = [...state.mensajes];
              const last = { ...msgs[msgs.length - 1] };
              last.archivos = data.archivos;
              last.proyecto = data.proyecto;
              last.streaming = false;
              msgs[msgs.length - 1] = last;
              return { mensajes: msgs };
            });
          }
        }
      }

      // Agregar respuesta del agente al contexto
      agregarContexto({
        rol: "assistant",
        contenido: resumenFinal || `Proyecto generado exitosamente`,
      });
    } catch {
      agregarMensaje({
        rol: "agente",
        texto: "❌ Error al conectar con el agente.",
      });
    } finally {
      setCargando(false);
    }
  };

  const enviarAnalisis = async () => {
    if (!repoUrl.trim()) return;
    agregarMensaje({ rol: "usuario", texto: `Analizar repo: ${repoUrl}` });
    limpiarInput();
    setCargando(true);

    try {
      const res = await fetch(`${API}/analizar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl }),
      });
      const data = await res.json();
      agregarMensaje({
        rol: "agente",
        texto: data.mensaje,
        archivos: data.archivos,
        proyecto: data.proyecto,
      });
    } catch {
      agregarMensaje({ rol: "agente", texto: "❌ Error al analizar el repo." });
    } finally {
      setCargando(false);
    }
  };

  const enviar = () => (modo === "nuevo" ? enviarStream() : enviarAnalisis());

  const descargar = async (proyecto: string) => {
    const res = await fetch(`${API}/descargar/${proyecto}`);
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `${proyecto}.zip`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  const cargarProyecto = (proyecto: Proyecto) => {
    agregarMensaje({
      rol: "agente",
      texto: `📂 Proyecto '${proyecto.nombre}' cargado desde el historial.`,
      archivos: proyecto.archivos,
      proyecto: proyecto.nombre,
      streaming: false,
    });
    setProyectoActivo(proyecto.nombre);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      enviar();
    }
  };

  const modos: { id: Modo; label: string; icon: React.ReactNode }[] = [
    { id: "nuevo", label: "Nuevo proyecto", icon: <RiSparklingFill /> },
    { id: "analizar", label: "Analizar repo", icon: <RiSearchLine /> },
  ];

  return (
    <div className="flex flex-col h-screen bg-[#0a0a0f] text-slate-200 font-sans">
      {/* Header */}
      <div className="px-6 py-4 bg-[#0f0f1a] border-b border-slate-800/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-violet-600/20 border border-violet-500/30 flex items-center justify-center">
              <RiCodeSSlashLine className="text-violet-400 text-lg" />
            </div>
            <div>
              <h1 className="text-base font-bold text-white leading-none">
                MERN Dev Agent
              </h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Powered by LangGraph + Groq
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Proyecto activo */}
            {proyectoActivo && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-violet-600/10 border border-violet-500/20 rounded-xl">
                <div className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
                <span className="text-xs text-violet-300 font-medium">
                  {proyectoActivo}
                </span>
                <button
                  onClick={limpiarConversacion}
                  className="text-slate-500 hover:text-red-400 transition-colors cursor-pointer ml-1"
                  title="Nueva conversación"
                >
                  <RiDeleteBin6Line className="text-xs" />
                </button>
              </div>
            )}

            {/* Selector de modo */}
            <div className="flex gap-2 bg-slate-900/80 p-1 rounded-xl border border-slate-800">
              {modos.map((m) => (
                <button
                  key={m.id}
                  onClick={() => setModo(m.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                    modo === m.id
                      ? "bg-violet-600 text-white shadow-lg shadow-violet-500/20"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {m.icon}
                  {m.label}
                </button>
              ))}
            </div>

            {/* Menú de perfil */}
            <div className="relative">
              <button
                onClick={() => setMenuPerfil(!menuPerfil)}
                className="flex items-center gap-2 px-3 py-2 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700/50 rounded-xl transition-all cursor-pointer"
              >
                <div className="w-6 h-6 rounded-lg bg-violet-600/30 border border-violet-500/30 flex items-center justify-center">
                  <RiUser3Line className="text-violet-400 text-xs" />
                </div>
                <span className="text-xs text-slate-300 font-medium">
                  {usuario?.nombre}
                </span>
                <RiArrowDownSLine className="text-slate-500 text-sm" />
              </button>

              {/* Dropdown */}
              <AnimatePresence>
                {menuPerfil && (
                  <motion.div
                    initial={{ opacity: 0, y: -10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -10, scale: 0.95 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 top-12 w-64 bg-slate-900 border border-slate-700/50 rounded-2xl shadow-xl z-50 overflow-hidden"
                  >
                    {/* Info usuario */}
                    <div className="px-4 py-3 border-b border-slate-700/50">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-violet-600/20 border border-violet-500/30 flex items-center justify-center">
                          <RiUser3Line className="text-violet-400" />
                        </div>
                        <div>
                          <p className="text-sm font-bold text-white">
                            {usuario?.nombre}
                          </p>
                          <p className="text-xs text-slate-500">
                            {usuario?.email}
                          </p>
                        </div>
                      </div>
                      <div className="mt-2 px-2 py-1 bg-violet-600/10 border border-violet-500/20 rounded-lg">
                        <span className="text-xs text-violet-300">
                          ✨ Plan {usuario?.plan === "free" ? "Free" : "Pro"}
                        </span>
                      </div>
                    </div>

                    {/* Opciones */}
                    <div className="py-2">
                      <button
                        onClick={() => setMenuPerfil(false)}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800/60 hover:text-white transition-colors cursor-pointer"
                      >
                        <RiSettings4Line className="text-slate-500" />
                        Configuración
                      </button>
                      <button
                        onClick={() => setMenuPerfil(false)}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800/60 hover:text-white transition-colors cursor-pointer"
                      >
                        <RiGlobalLine className="text-slate-500" />
                        Idioma — Español
                      </button>
                      <button
                        onClick={() => setMenuPerfil(false)}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800/60 hover:text-white transition-colors cursor-pointer"
                      >
                        <RiQuestionLine className="text-slate-500" />
                        Obtener ayuda
                      </button>

                      <div className="mx-4 my-2 border-t border-slate-700/50" />

                      {/* Mejorar plan */}
                      <button
                        onClick={() => setMenuPerfil(false)}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-violet-300 hover:bg-violet-600/10 transition-colors cursor-pointer"
                      >
                        <RiVipCrownLine className="text-violet-400" />
                        Mejorar a Pro
                        <span className="ml-auto text-xs bg-violet-600/20 border border-violet-500/30 px-2 py-0.5 rounded-lg">
                          $29/mes
                        </span>
                      </button>

                      <div className="mx-4 my-2 border-t border-slate-700/50" />

                      {/* Cerrar sesión */}
                      <button
                        onClick={() => {
                          cerrarSesion();
                          setMenuPerfil(false);
                        }}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-400 hover:bg-red-400/10 transition-colors cursor-pointer"
                      >
                        <RiLogoutBoxLine className="text-red-400" />
                        Cerrar sesión
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <ProjectHistory onCargar={cargarProyecto} />

        {/* Chat */}
        <div className="flex flex-col flex-1 overflow-hidden">
          <div ref={chatRef} className="flex-1 overflow-y-auto px-6 py-6">
            <div className="max-w-3xl mx-auto flex flex-col gap-6">
              {mensajes.length === 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col items-center justify-center mt-20 gap-4 text-center"
                >
                  <div className="w-16 h-16 rounded-2xl bg-violet-600/20 border border-violet-500/30 flex items-center justify-center">
                    <RiRobot2Line className="text-violet-400 text-3xl" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-white">
                      {modo === "nuevo"
                        ? "¿Qué app necesita tu cliente?"
                        : "¿Qué repo querés analizar?"}
                    </h2>
                    <p className="text-sm text-slate-500 mt-2">
                      {modo === "nuevo"
                        ? "Describí la app y el agente genera el proyecto MERN completo con seguridad y Docker"
                        : "Pegá la URL de un repo de GitHub y el agente lo analiza en profundidad"}
                    </p>
                  </div>

                  {modo === "nuevo" && (
                    <div className="flex flex-wrap gap-2 justify-center mt-2">
                      {[
                        "App de ecommerce con carrito y pagos",
                        "Sistema de gestión de turnos médicos",
                        "Red social con posts y comentarios",
                        "Dashboard de analíticas con gráficos",
                      ].map((ejemplo) => (
                        <button
                          key={ejemplo}
                          onClick={() => setInstrucciones(ejemplo)}
                          className="px-3 py-1.5 text-xs bg-slate-800/80 hover:bg-slate-700 border border-slate-700 hover:border-violet-500/50 text-slate-400 hover:text-slate-200 rounded-lg transition-all cursor-pointer"
                        >
                          {ejemplo}
                        </button>
                      ))}
                    </div>
                  )}
                </motion.div>
              )}

              <AnimatePresence>
                {mensajes.map((msg, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                    className={`flex gap-3 ${msg.rol === "usuario" ? "flex-row-reverse" : "flex-row"}`}
                  >
                    <div
                      className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 ${
                        msg.rol === "usuario"
                          ? "bg-violet-600/20 border border-violet-500/30"
                          : "bg-slate-800 border border-slate-700"
                      }`}
                    >
                      {msg.rol === "usuario" ? (
                        <RiUser3Line className="text-violet-400 text-sm" />
                      ) : (
                        <RiRobot2Line className="text-slate-400 text-sm" />
                      )}
                    </div>

                    <div
                      className={`flex flex-col gap-3 max-w-[80%] ${msg.rol === "usuario" ? "items-end" : "items-start"}`}
                    >
                      <div
                        className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                          msg.rol === "usuario"
                            ? "bg-violet-600 text-white rounded-tr-sm"
                            : "bg-slate-800/80 border border-slate-700/50 text-slate-200 rounded-tl-sm"
                        }`}
                      >
                        <pre className="whitespace-pre-wrap font-sans">
                          {msg.texto}
                          {msg.streaming && (
                            <span className="inline-block w-2 h-4 bg-violet-400 ml-1 animate-pulse rounded-sm" />
                          )}
                        </pre>
                      </div>

                      {msg.archivos &&
                        msg.archivos.length > 0 &&
                        !msg.streaming && (
                          <div className="flex flex-wrap gap-1.5">
                            {msg.archivos.map((a, j) => (
                              <span
                                key={j}
                                className="flex items-center gap-1 bg-slate-900 border border-slate-700/50 text-violet-400 text-xs px-2 py-1 rounded-lg"
                              >
                                <RiCodeSSlashLine className="text-xs" />
                                {a}
                              </span>
                            ))}
                          </div>
                        )}

                      {msg.proyecto &&
                        msg.rol === "agente" &&
                        !msg.streaming &&
                        msg.proyecto.length > 0 && (
                          <div className="flex flex-col gap-2 w-full">
                            <div className="flex flex-wrap gap-2">
                              <button
                                onClick={() => descargar(msg.proyecto!)}
                                className="flex items-center gap-2 bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/30 hover:border-violet-500/60 text-violet-300 text-xs font-medium px-4 py-2 rounded-xl transition-all cursor-pointer"
                              >
                                <RiDownload2Line />
                                Descargar {msg.proyecto}.zip
                              </button>
                            </div>
                            <TestGenerator
                              proyecto={msg.proyecto!}
                              instrucciones={msg.texto}
                            />
                            <GithubExport
                              proyecto={msg.proyecto!}
                              onExportado={(url) => {
                                useAgentStore.setState((state) => {
                                  const msgs = [...state.mensajes];
                                  msgs[i] = { ...msgs[i], repoGithub: url };
                                  return { mensajes: msgs };
                                });
                              }}
                            />
                            <DeployRender
                              proyecto={msg.proyecto!}
                              repoUrl={msg.repoGithub || ""}
                            />
                            <FileViewer
                              proyecto={msg.proyecto}
                              archivos={msg.archivos || []}
                            />
                          </div>
                        )}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </div>

          {/* Input */}
          <div className="px-6 py-4 bg-[#0f0f1a] border-t border-slate-800/50">
            <div className="max-w-3xl mx-auto">
              {/* Indicador de contexto activo */}
              {proyectoActivo && (
                <div className="flex items-center gap-2 mb-2 px-3 py-1.5 bg-slate-900/60 border border-slate-700/50 rounded-xl">
                  <div className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
                  <span className="text-xs text-slate-400">
                    Continuando sobre{" "}
                    <span className="text-violet-300 font-medium">
                      {proyectoActivo}
                    </span>{" "}
                    — podés pedir modificaciones directamente
                  </span>
                </div>
              )}

              <div className="flex gap-3 bg-slate-900/80 border border-slate-700/50 rounded-2xl p-2 focus-within:border-violet-500/50 transition-all">
                {modo === "nuevo" ? (
                  <textarea
                    className="flex-1 bg-transparent px-3 py-2 text-sm text-slate-200 resize-none outline-none placeholder-slate-600"
                    value={instrucciones}
                    onChange={(e) => setInstrucciones(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={
                      proyectoActivo
                        ? `Pedí una modificación sobre '${proyectoActivo}'...`
                        : "Describí la app del cliente... (Enter para enviar)"
                    }
                    rows={2}
                  />
                ) : (
                  <div className="flex-1 flex items-center gap-2 px-3">
                    <RiGithubFill className="text-slate-500 text-lg flex-shrink-0" />
                    <input
                      className="flex-1 bg-transparent py-2 text-sm text-slate-200 outline-none placeholder-slate-600"
                      value={repoUrl}
                      onChange={(e) => setRepoUrl(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="https://github.com/usuario/repo"
                    />
                  </div>
                )}
                <button
                  onClick={enviar}
                  disabled={cargando}
                  className={`flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer ${
                    cargando
                      ? "bg-slate-700 text-slate-500 cursor-not-allowed"
                      : "bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-500/20"
                  }`}
                >
                  <RiSendPlaneFill />
                  {cargando
                    ? "Generando..."
                    : modo === "nuevo"
                      ? "Generar"
                      : "Analizar"}
                </button>
              </div>
              <p className="text-xs text-slate-600 text-center mt-2">
                Enter para enviar · Shift+Enter para nueva línea
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
