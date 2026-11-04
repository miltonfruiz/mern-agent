import { useState } from "react";
import { motion } from "framer-motion";
import { RiTestTubeLine, RiCheckLine, RiLoader4Line } from "react-icons/ri";

interface TestGeneratorProps {
  proyecto: string;
  instrucciones: string;
}

const API = "http://127.0.0.1:8000";

export default function TestGenerator({
  proyecto,
  instrucciones,
}: TestGeneratorProps) {
  const [generando, setGenerando] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [completado, setCompletado] = useState(false);
  const [abierto, setAbierto] = useState(false);

  const generarTests = async () => {
    setAbierto(true);
    setGenerando(true);
    setLogs([]);
    setCompletado(false);

    try {
      const res = await fetch(`${API}/generar/tests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre_proyecto: proyecto, instrucciones }),
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
            data.tipo === "archivo" ||
            data.tipo === "archivo_ok" ||
            data.tipo === "estado"
          ) {
            setLogs((prev) => [...prev, data.texto]);
          }
          if (data.tipo === "finalizado") {
            setCompletado(true);
          }
        }
      }
    } catch {
      setLogs((prev) => [...prev, "❌ Error al generar tests"]);
    } finally {
      setGenerando(false);
    }
  };

  return (
    <div className="mt-2">
      <button
        onClick={generarTests}
        disabled={generando}
        className={`flex items-center gap-2 text-xs font-medium px-4 py-2 rounded-xl transition-all cursor-pointer ${
          completado
            ? "bg-emerald-600/20 border border-emerald-500/30 text-emerald-300"
            : "bg-slate-700/60 hover:bg-slate-600/60 border border-slate-600/50 text-slate-300"
        }`}
      >
        {generando ? (
          <RiLoader4Line className="animate-spin" />
        ) : completado ? (
          <RiCheckLine />
        ) : (
          <RiTestTubeLine />
        )}
        {generando
          ? "Generando tests..."
          : completado
            ? "Tests generados ✅"
            : "🧪 Generar tests"}
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
                  : log.startsWith("⚙️")
                    ? "text-violet-400"
                    : "text-slate-400"
              }`}
            >
              {log}
            </div>
          ))}
          {completado && (
            <div className="mt-3 pt-3 border-t border-slate-700/50 text-emerald-400">
              ✅ Tests generados en ./proyectos/{proyecto}/backend/tests/
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}
