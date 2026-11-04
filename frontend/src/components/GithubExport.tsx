import { useState } from "react";
import { motion } from "framer-motion";
import {
  RiGithubFill,
  RiCheckLine,
  RiLoader4Line,
  RiExternalLinkLine,
} from "react-icons/ri";

interface GithubExportProps {
  proyecto: string;
  onExportado?: (url: string) => void;
}

const API = "http://127.0.0.1:8000";

export default function GithubExport({
  proyecto,
  onExportado,
}: GithubExportProps) {
  const [exportando, setExportando] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [completado, setCompletado] = useState(false);
  const [repoUrl, setRepoUrl] = useState("");
  const [abierto, setAbierto] = useState(false);

  const exportar = async () => {
    setAbierto(true);
    setExportando(true);
    setLogs([]);
    setCompletado(false);
    setRepoUrl("");

    try {
      const res = await fetch(`${API}/exportar/github`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre_proyecto: proyecto }),
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

          if (
            data.tipo === "estado" ||
            data.tipo === "archivo_ok" ||
            data.tipo === "archivo"
          ) {
            setLogs((prev) => [...prev, data.texto]);
          }

          if (data.tipo === "error") {
            setLogs((prev) => [...prev, data.texto]);
            setExportando(false);
          }

          if (data.tipo === "finalizado") {
            setRepoUrl(data.repo_url);
            setCompletado(true);
            onExportado?.(data.repo_url);
          }
        }
      }
    } catch {
      setLogs((prev) => [...prev, "❌ Error al conectar con el servidor"]);
    } finally {
      setExportando(false);
    }
  };

  return (
    <div className="mt-2">
      <button
        onClick={exportar}
        disabled={exportando}
        className={`flex items-center gap-2 text-xs font-medium px-4 py-2 rounded-xl transition-all cursor-pointer ${
          completado
            ? "bg-emerald-600/20 border border-emerald-500/30 text-emerald-300"
            : "bg-slate-700/60 hover:bg-slate-600/60 border border-slate-600/50 text-slate-300"
        }`}
      >
        {exportando ? (
          <RiLoader4Line className="animate-spin" />
        ) : completado ? (
          <RiCheckLine />
        ) : (
          <RiGithubFill />
        )}
        {exportando
          ? "Exportando a GitHub..."
          : completado
            ? "Exportado a GitHub ✅"
            : "🐙 Exportar a GitHub"}
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

          {completado && repoUrl && (
            <div className="mt-3 pt-3 border-t border-slate-700/50 flex items-center gap-2">
              <RiGithubFill className="text-slate-400" />
              <a
                href={repoUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-violet-400 hover:text-violet-300 transition-colors flex items-center gap-1"
              >
                {repoUrl}
                <RiExternalLinkLine />
              </a>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}
