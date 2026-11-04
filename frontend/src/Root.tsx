import { useState, useEffect } from "react";
import App from "./App";
import Login from "./pages/Login";
import Register from "./pages/Register";
import { useAuthStore } from "./store/useAuthStore";

const API = "http://127.0.0.1:8000";

export default function Root() {
  const { token, setUsuario, cerrarSesion, estaAutenticado } = useAuthStore();
  const [pantalla, setPantalla] = useState<"login" | "registro">("login");
  const [verificando, setVerificando] = useState(true);

  useEffect(() => {
    const verificarToken = async () => {
      if (!token) {
        setVerificando(false);
        return;
      }
      try {
        const res = await fetch(`${API}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setUsuario(data, token);
        } else {
          cerrarSesion();
        }
      } catch {
        cerrarSesion();
      } finally {
        setVerificando(false);
      }
    };
    verificarToken();
  }, []);

  if (verificando) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!estaAutenticado()) {
    return pantalla === "login" ? (
      <Login onIrARegistro={() => setPantalla("registro")} />
    ) : (
      <Register onIrALogin={() => setPantalla("login")} />
    );
  }

  return <App />;
}
