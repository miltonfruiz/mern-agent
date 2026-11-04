import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  RiEditLine,
  RiEyeLine,
  RiSaveLine,
  RiFileCopyLine,
  RiCheckLine,
  RiFolder3Line,
  RiArrowDownSLine,
  RiArrowRightSLine,
} from "react-icons/ri";

interface FileViewerProps {
  proyecto: string;
  archivos: string[];
}

const extensionLenguaje: Record<string, string> = {
  js: "javascript",
  jsx: "jsx",
  ts: "typescript",
  tsx: "tsx",
  json: "json",
  md: "markdown",
  yml: "yaml",
  yaml: "yaml",
  css: "css",
  html: "html",
  py: "python",
  sh: "bash",
  env: "bash",
};

const extensionIcono: Record<string, string> = {
  js: "🟨",
  jsx: "⚛️",
  ts: "🔷",
  tsx: "⚛️",
  json: "📋",
  md: "📝",
  yml: "🐳",
  yaml: "🐳",
  css: "🎨",
  html: "🌐",
  py: "🐍",
  env: "🔒",
  Dockerfile: "🐳",
};

function getExtension(filename: string): string {
  if (filename.includes("Dockerfile")) return "Dockerfile";
  if (filename.includes(".env")) return "env";
  return filename.split(".").pop() || "txt";
}

function getLenguaje(filename: string): string {
  return extensionLenguaje[getExtension(filename)] || "text";
}

function getIcono(filename: string): string {
  return extensionIcono[getExtension(filename)] || "📄";
}

function buildTree(archivos: string[]) {
  const tree: Record<string, string[]> = {};
  archivos.forEach((archivo) => {
    const partes = archivo.split("/");
    if (partes.length === 1) {
      if (!tree["/"]) tree["/"] = [];
      tree["/"].push(archivo);
    } else {
      const carpeta = partes.slice(0, -1).join("/");
      if (!tree[carpeta]) tree[carpeta] = [];
      tree[carpeta].push(archivo);
    }
  });
  return tree;
}

const API = "http://127.0.0.1:8000";

export default function FileViewer({ proyecto, archivos }: FileViewerProps) {
  const [abierto, setAbierto] = useState(false);
  const [tabs, setTabs] = useState<string[]>([]);
  const [tabActiva, setTabActiva] = useState<string>("");
  const [contenidos, setContenidos] = useState<Record<string, string>>({});
  const [editados, setEditados] = useState<Record<string, string>>({});
  const [modoEdicion, setModoEdicion] = useState<Record<string, boolean>>({});
  const [guardando, setGuardando] = useState<string>("");
  const [guardado, setGuardado] = useState<string>("");
  const [copiado, setCopiado] = useState<string>("");
  const [carpetasAbiertas, setCarpetasAbiertas] = useState<
    Record<string, boolean>
  >({
    backend: true,
    "backend/middleware": true,
    "backend/models": true,
    "backend/routes": true,
    "backend/controllers": true,
    "frontend/src": true,
    "/": true,
  });

  const tree = buildTree(archivos);

  const abrirArchivo = async (archivo: string) => {
    if (!tabs.includes(archivo)) {
      setTabs((prev) => [...prev, archivo]);
    }
    setTabActiva(archivo);

    if (!contenidos[archivo]) {
      try {
        const res = await fetch(`${API}/archivo/${proyecto}/${archivo}`);
        const data = await res.json();
        setContenidos((prev) => ({ ...prev, [archivo]: data.contenido }));
        setEditados((prev) => ({ ...prev, [archivo]: data.contenido }));
      } catch {
        setContenidos((prev) => ({
          ...prev,
          [archivo]: "❌ Error al cargar el archivo",
        }));
      }
    }
  };

  const cerrarTab = (archivo: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const nuevasTabs = tabs.filter((t) => t !== archivo);
    setTabs(nuevasTabs);
    if (tabActiva === archivo) {
      setTabActiva(nuevasTabs[nuevasTabs.length - 1] || "");
    }
  };

  const toggleEdicion = (archivo: string) => {
    setModoEdicion((prev) => ({ ...prev, [archivo]: !prev[archivo] }));
    if (!editados[archivo]) {
      setEditados((prev) => ({ ...prev, [archivo]: contenidos[archivo] }));
    }
  };

  const guardar = async (archivo: string) => {
    setGuardando(archivo);
    try {
      await fetch(`${API}/archivo/${proyecto}/${archivo}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contenido: editados[archivo] }),
      });
      setContenidos((prev) => ({ ...prev, [archivo]: editados[archivo] }));
      setModoEdicion((prev) => ({ ...prev, [archivo]: false }));
      setGuardado(archivo);
      setTimeout(() => setGuardado(""), 2000);
    } catch {
      alert("❌ Error al guardar el archivo");
    } finally {
      setGuardando("");
    }
  };

  const copiar = async (texto: string, archivo: string) => {
    await navigator.clipboard.writeText(texto);
    setCopiado(archivo);
    setTimeout(() => setCopiado(""), 2000);
  };

  const toggleCarpeta = (carpeta: string) => {
    setCarpetasAbiertas((prev) => ({ ...prev, [carpeta]: !prev[carpeta] }));
  };

  const tienecambios = (archivo: string) =>
    editados[archivo] !== undefined &&
    editados[archivo] !== contenidos[archivo];

  const nombreArchivo = (ruta: string) => ruta.split("/").pop() || ruta;

  return (
    <div className="mt-2 w-full">
      <button
        onClick={() => setAbierto(!abierto)}
        className="flex items-center gap-2 bg-slate-800/60 hover:bg-slate-700/60 border border-slate-700/50 text-slate-300 text-xs font-medium px-4 py-2 rounded-xl transition-all cursor-pointer w-full justify-between"
      >
        <div className="flex items-center gap-2">
          <RiFolder3Line className="text-violet-400" />
          <span>Explorador de archivos — {proyecto}</span>
          <span className="bg-slate-700 text-slate-400 px-1.5 py-0.5 rounded text-xs">
            {archivos.length} archivos
          </span>
        </div>
        <span className="text-slate-500">
          {abierto ? "▲ Cerrar" : "▼ Abrir"}
        </span>
      </button>

      {abierto && (
        <div
          className="mt-2 border border-slate-700/50 rounded-xl overflow-hidden flex"
          style={{ height: "540px" }}
        >
          {/* Árbol de archivos */}
          <div className="w-56 bg-slate-900/80 border-r border-slate-700/50 overflow-y-auto flex-shrink-0">
            <div className="px-3 py-2 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-slate-700/50">
              📁 {proyecto}
            </div>
            <div className="py-1">
              {Object.entries(tree).map(([carpeta, files]) => (
                <div key={carpeta}>
                  {carpeta !== "/" && (
                    <button
                      onClick={() => toggleCarpeta(carpeta)}
                      className="w-full flex items-center gap-1 px-3 py-1 text-xs text-slate-500 hover:text-slate-300 hover:bg-slate-800/60 transition-colors cursor-pointer"
                    >
                      {carpetasAbiertas[carpeta] ? (
                        <RiArrowDownSLine />
                      ) : (
                        <RiArrowRightSLine />
                      )}
                      <span>📁 {carpeta}</span>
                    </button>
                  )}
                  {(carpeta === "/" || carpetasAbiertas[carpeta]) &&
                    files.map((archivo) => (
                      <button
                        key={archivo}
                        onClick={() => abrirArchivo(archivo)}
                        className={`w-full flex items-center gap-2 text-left py-1.5 text-xs transition-colors cursor-pointer ${
                          tabActiva === archivo
                            ? "bg-slate-700/80 text-white"
                            : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                        }`}
                        style={{
                          paddingLeft: carpeta === "/" ? "12px" : "24px",
                        }}
                      >
                        <span>{getIcono(archivo)}</span>
                        <span className="truncate">
                          {nombreArchivo(archivo)}
                        </span>
                        {tienecambios(archivo) && (
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0 ml-auto mr-2" />
                        )}
                      </button>
                    ))}
                </div>
              ))}
            </div>
          </div>

          {/* Editor / Visor */}
          <div className="flex-1 flex flex-col bg-[#020817] overflow-hidden">
            {/* Tabs */}
            {tabs.length > 0 && (
              <div className="flex overflow-x-auto bg-slate-900/80 border-b border-slate-700/50 flex-shrink-0">
                {tabs.map((tab) => (
                  <div
                    key={tab}
                    onClick={() => setTabActiva(tab)}
                    className={`flex items-center gap-2 px-4 py-2 text-xs cursor-pointer border-r border-slate-700/50 flex-shrink-0 transition-colors ${
                      tabActiva === tab
                        ? "bg-[#020817] text-white border-t-2 border-t-violet-500"
                        : "text-slate-500 hover:text-slate-300 hover:bg-slate-800/60"
                    }`}
                  >
                    <span>{getIcono(tab)}</span>
                    <span>{nombreArchivo(tab)}</span>
                    {tienecambios(tab) && (
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                    )}
                    <button
                      onClick={(e) => cerrarTab(tab, e)}
                      className="ml-1 text-slate-600 hover:text-slate-300 transition-colors"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Toolbar */}
            {tabActiva && contenidos[tabActiva] && (
              <div className="flex items-center justify-between px-4 py-2 bg-slate-900/60 border-b border-slate-700/50 flex-shrink-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">{tabActiva}</span>
                  <span className="px-2 py-0.5 bg-slate-800 rounded text-slate-400 text-xs">
                    {getLenguaje(tabActiva)}
                  </span>
                  {tienecambios(tabActiva) && (
                    <span className="text-xs text-amber-400">
                      ● Sin guardar
                    </span>
                  )}
                  {guardado === tabActiva && (
                    <span className="text-xs text-emerald-400 flex items-center gap-1">
                      <RiCheckLine /> Guardado
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() =>
                      copiar(
                        modoEdicion[tabActiva]
                          ? editados[tabActiva]
                          : contenidos[tabActiva],
                        tabActiva,
                      )
                    }
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-all cursor-pointer"
                  >
                    {copiado === tabActiva ? (
                      <RiCheckLine className="text-emerald-400" />
                    ) : (
                      <RiFileCopyLine />
                    )}
                    {copiado === tabActiva ? "Copiado" : "Copiar"}
                  </button>

                  {modoEdicion[tabActiva] ? (
                    <>
                      <button
                        onClick={() => toggleEdicion(tabActiva)}
                        className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-all cursor-pointer"
                      >
                        <RiEyeLine />
                        Vista previa
                      </button>
                      <button
                        onClick={() => guardar(tabActiva)}
                        disabled={
                          guardando === tabActiva || !tienecambios(tabActiva)
                        }
                        className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all cursor-pointer font-medium ${
                          tienecambios(tabActiva)
                            ? "bg-violet-600 hover:bg-violet-500 text-white"
                            : "bg-slate-800 text-slate-600 cursor-not-allowed"
                        }`}
                      >
                        <RiSaveLine />
                        {guardando === tabActiva ? "Guardando..." : "Guardar"}
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => toggleEdicion(tabActiva)}
                      className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/30 text-violet-300 rounded-lg transition-all cursor-pointer"
                    >
                      <RiEditLine />
                      Editar
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Contenido */}
            {tabActiva && contenidos[tabActiva] ? (
              <div className="flex-1 overflow-auto">
                {modoEdicion[tabActiva] ? (
                  <textarea
                    className="w-full h-full bg-[#020817] text-slate-200 text-xs font-mono p-4 outline-none resize-none leading-relaxed"
                    value={editados[tabActiva] ?? contenidos[tabActiva]}
                    onChange={(e) =>
                      setEditados((prev) => ({
                        ...prev,
                        [tabActiva]: e.target.value,
                      }))
                    }
                    spellCheck={false}
                  />
                ) : (
                  <SyntaxHighlighter
                    language={getLenguaje(tabActiva)}
                    style={vscDarkPlus}
                    showLineNumbers
                    customStyle={{
                      margin: 0,
                      borderRadius: 0,
                      fontSize: "12px",
                      background: "#020817",
                      minHeight: "100%",
                    }}
                  >
                    {editados[tabActiva] ?? contenidos[tabActiva]}
                  </SyntaxHighlighter>
                )}
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-slate-600 text-sm">
                {tabs.length === 0
                  ? "← Seleccioná un archivo para verlo"
                  : "⏳ Cargando..."}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
