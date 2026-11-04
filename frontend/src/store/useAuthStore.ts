import { create } from "zustand";

export interface Usuario {
  id: string;
  nombre: string;
  email: string;
  rol: string;
  plan: string;
}

interface AuthStore {
  usuario: Usuario | null;
  token: string | null;
  setUsuario: (usuario: Usuario, token: string) => void;
  cerrarSesion: () => void;
  estaAutenticado: () => boolean;
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  usuario: null,
  token: localStorage.getItem("token"),
  setUsuario: (usuario, token) => {
    localStorage.setItem("token", token);
    set({ usuario, token });
  },
  cerrarSesion: () => {
    localStorage.removeItem("token");
    set({ usuario: null, token: null });
  },
  estaAutenticado: () => !!get().token,
}));
