import { useState } from "react";
import { motion } from "framer-motion";
import {
  RiRocketLine,
  RiCheckLine,
  RiLoader4Line,
  RiExternalLinkLine,
  RiServerLine,
  RiGlobalLine,
} from "react-icons/ri";

interface DeployRenderProps {
  proyecto: string;
  repoUrl: string;
}

const API = "http://127.0.0.1:8000";

export default function DeployRender({ proyecto, repoUrl }: DeployRenderProps) {
  const [deployando, setDesplegando] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [completado, setCompletado] = useState(false);
  const [backendUrl, setBackendUrl] = useState("");
  const [frontendUrl, setFrontendUrl] = useState("");
  const [abierto, setAbierto] = useState(false);

  const deploy = async () => {
    setAbierto(true);
    setDesplegando(true);
    setLogs([]);
    setCompletado(false);

    try {
      const res = await fetch(`${API}/deploy/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nombre_proyecto: proyecto,
          repo_url: repoUrl,
        }),
      });

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n").filter((l) => l.startsWith("data: "));

        for (const line of lines) {
          const data = JSON.parse(line.replace("data: ", ""));

          if (data.tipo === "estado" || data.tipo === "error") {
            setLogs((prev) => [...prev, data.texto]);
          }

          if (data.tipo === "finalizado") {
            setBackendUrl(data.backend_url);
            setFrontendUrl(data.frontend_url);
            setCompletado(true);
          }
        }
      }
    } catch {
      setLogs((prev) => [...prev, "❌ Error al conectar con el servidor"]);
    } finally {
      setDesplegando(false);
    }
  };

  return (
    <div className="mt-2">
      <button
        onClick={deploy}
        disabled={deployando || !repoUrl}
        className={`flex items-center gap-2 text-xs font-medium px-4 py-2 rounded-xl transition-all cursor-pointer ${
          completado
            ? "bg-emerald-600/20 border border-emerald-500/30 text-emerald-300"
            : !repoUrl
              ? "bg-slate-800/40 border border-slate-700/30 text-slate-600 cursor-not-allowed"
              : "bg-orange-600/20 hover:bg-orange-600/30 border border-orange-500/30 text-orange-300"
        }`}
      >
        {deployando ? (
          <RiLoader4Line className="animate-spin" />
        ) : completado ? (
          <RiCheckLine />
        ) : (
          <RiRocketLine />
        )}
        {deployando
          ? "Desplegando en Render..."
          : completado
            ? "Deployed en Render ✅"
            : !repoUrl
              ? "🚀 Deploy (exportá a GitHub primero)"
              : "🚀 Deploy en Render"}
      </button>

      {abierto && logs.length > 0 && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="mt-2 bg-slate-900/80 border border-slate-700/50 rounded-xl p-4 font-mono text-xs"
        >
          {logs.map((log, i) => (
            <div
              key={i}
              className={`py-0.5 ${
                log.startsWith("✅")
                  ? "text-emerald-400"
                  : log.startsWith("❌")
                    ? "text-red-400"
                    : log.startsWith("⚠️")
                      ? "text-amber-400"
                      : "text-slate-400"
              }`}
            >
              {log}
            </div>
          ))}

          {completado && (
            <div className="mt-3 pt-3 border-t border-slate-700/50 flex flex-col gap-2">
              <a
                href={backendUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-violet-400 hover:text-violet-300 transition-colors"
              >
                <RiServerLine />
                Backend: {backendUrl}
                <RiExternalLinkLine />
              </a>
              <a
                href={frontendUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-emerald-400 hover:text-emerald-300 transition-colors"
              >
                <RiGlobalLine />
                Frontend: {frontendUrl}
                <RiExternalLinkLine />
              </a>
              <p className="text-slate-500 mt-1">
                ⏳ El build tarda 2-5 minutos en Render. Las URLs estarán
                activas pronto.
              </p>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}
