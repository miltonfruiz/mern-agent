import { create } from "zustand";

export type Rol = "usuario" | "agente";
export type Modo = "nuevo" | "analizar";

export interface Mensaje {
  rol: Rol;
  texto: string;
  archivos?: string[];
  proyecto?: string;
  streaming?: boolean;
  repoGithub?: string;
}

export interface MensajeContexto {
  rol: "user" | "assistant";
  contenido: string;
}

interface AgentStore {
  modo: Modo;
  mensajes: Mensaje[];
  contexto: MensajeContexto[];
  cargando: boolean;
  instrucciones: string;
  repoUrl: string;
  proyectoActivo: string;
  setModo: (modo: Modo) => void;
  setInstrucciones: (texto: string) => void;
  setRepoUrl: (url: string) => void;
  agregarMensaje: (msg: Mensaje) => void;
  agregarContexto: (msg: MensajeContexto) => void;
  setCargando: (valor: boolean) => void;
  setProyectoActivo: (nombre: string) => void;
  limpiarInput: () => void;
  limpiarConversacion: () => void;
}

export const useAgentStore = create<AgentStore>((set) => ({
  modo: "nuevo",
  mensajes: [],
  contexto: [],
  cargando: false,
  instrucciones: "",
  repoUrl: "",
  proyectoActivo: "",
  setModo: (modo) => set({ modo }),
  setInstrucciones: (instrucciones) => set({ instrucciones }),
  setRepoUrl: (repoUrl) => set({ repoUrl }),
  agregarMensaje: (msg) =>
    set((state) => ({ mensajes: [...state.mensajes, msg] })),
  agregarContexto: (msg) =>
    set((state) => ({ contexto: [...state.contexto, msg] })),
  setCargando: (cargando) => set({ cargando }),
  setProyectoActivo: (proyectoActivo) => set({ proyectoActivo }),
  limpiarInput: () => set({ instrucciones: "", repoUrl: "" }),
  limpiarConversacion: () =>
    set({ mensajes: [], contexto: [], proyectoActivo: "" }),
}));
