import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  RiFolder3Line,
  RiDeleteBin6Line,
  RiDownload2Line,
  RiTimeLine,
  RiRefreshLine,
  RiCodeSSlashLine,
} from "react-icons/ri";

interface Proyecto {
  nombre: string;
  archivos: string[];
  creado: number;
}

interface ProjectHistoryProps {
  onCargar: (proyecto: Proyecto) => void;
}

const API = "http://127.0.0.1:8000";

function formatFecha(timestamp: number): string {
  const fecha = new Date(timestamp * 1000);
  return fecha.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ProjectHistory({ onCargar }: ProjectHistoryProps) {
  const [proyectos, setProyectos] = useState<Proyecto[]>([]);
  const [cargando, setCargando] = useState(false);
  const [eliminando, setEliminando] = useState<string>("");

  const cargarHistorial = async () => {
    setCargando(true);
    try {
      const res = await fetch(`${API}/proyectos`);
      const data = await res.json();
      setProyectos(data.proyectos);
    } catch {
      console.error("Error al cargar historial");
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargarHistorial();
  }, []);

  const eliminar = async (nombre: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEliminando(nombre);
    try {
      await fetch(`${API}/proyectos/${nombre}`, { method: "DELETE" });
      setProyectos((prev) => prev.filter((p) => p.nombre !== nombre));
    } catch {
      console.error("Error al eliminar");
    } finally {
      setEliminando("");
    }
  };

  const descargar = async (nombre: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const res = await fetch(`${API}/descargar/${nombre}`);
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `${nombre}.zip`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="w-64 bg-[#0f0f1a] border-r border-slate-800/50 flex flex-col flex-shrink-0">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <RiFolder3Line className="text-violet-400 text-sm" />
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
            Proyectos
          </span>
        </div>
        <button
          onClick={cargarHistorial}
          className="text-slate-500 hover:text-violet-400 transition-colors cursor-pointer"
          title="Actualizar"
        >
          <RiRefreshLine
            className={`text-sm ${cargando ? "animate-spin" : ""}`}
          />
        </button>
      </div>

      {/* Lista */}
      <div className="flex-1 overflow-y-auto py-2">
        {proyectos.length === 0 && !cargando && (
          <div className="flex flex-col items-center justify-center mt-12 gap-2 text-center px-4">
            <RiFolder3Line className="text-slate-700 text-3xl" />
            <p className="text-xs text-slate-600">
              No hay proyectos generados aún
            </p>
          </div>
        )}

        <AnimatePresence>
          {proyectos.map((proyecto) => (
            <motion.div
              key={proyecto.nombre}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              onClick={() => onCargar(proyecto)}
              className="group mx-2 mb-1 px-3 py-3 rounded-xl hover:bg-slate-800/60 border border-transparent hover:border-slate-700/50 cursor-pointer transition-all"
            >
              {/* Nombre */}
              <div className="flex items-center gap-2 mb-1.5">
                <div className="w-6 h-6 rounded-lg bg-violet-600/20 border border-violet-500/20 flex items-center justify-center flex-shrink-0">
                  <RiCodeSSlashLine className="text-violet-400 text-xs" />
                </div>
                <span className="text-sm font-medium text-slate-200 truncate">
                  {proyecto.nombre}
                </span>
              </div>

              {/* Fecha */}
              <div className="flex items-center gap-1 mb-2 pl-8">
                <RiTimeLine className="text-slate-600 text-xs" />
                <span className="text-xs text-slate-600">
                  {formatFecha(proyecto.creado)}
                </span>
              </div>

              {/* Contador de archivos */}
              <div className="pl-8 mb-2">
                <span className="text-xs text-slate-500">
                  {proyecto.archivos.length} archivos
                </span>
              </div>

              {/* Acciones */}
              <div className="pl-8 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={(e) => descargar(proyecto.nombre, e)}
                  className="flex items-center gap-1 text-xs text-slate-400 hover:text-violet-400 transition-colors cursor-pointer"
                  title="Descargar ZIP"
                >
                  <RiDownload2Line />
                  ZIP
                </button>
                <button
                  onClick={(e) => eliminar(proyecto.nombre, e)}
                  className="flex items-center gap-1 text-xs text-slate-400 hover:text-red-400 transition-colors cursor-pointer"
                  title="Eliminar proyecto"
                >
                  {eliminando === proyecto.nombre ? (
                    <RiRefreshLine className="animate-spin" />
                  ) : (
                    <RiDeleteBin6Line />
                  )}
                  Eliminar
                </button>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
