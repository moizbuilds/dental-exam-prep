import { useState } from "react";
import { supabase } from "../supabaseClient";

export default function Login() {
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    const fn = mode === "signin" ? "signInWithPassword" : "signUp";
    const { error } = await supabase.auth[fn]({ email, password });
    if (error) setMsg({ type: "err", text: error.message });
    else if (mode === "signup")
      setMsg({ type: "ok", text: "Account created. You can sign in now." });
    setBusy(false);
  }

  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <h1>Dental Qualifying Exam Prep</h1>
        <p className="muted">MOPH/DHP National General Dental Qualifying Examination</p>
        <form onSubmit={submit}>
          <label>Email</label>
          <input type="email" value={email} required
                 onChange={(e) => setEmail(e.target.value)} />
          <label>Password</label>
          <input type="password" value={password} required minLength={6}
                 onChange={(e) => setPassword(e.target.value)} />
          <button className="btn primary" disabled={busy}>
            {busy ? "…" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
        </form>
        {msg && <p className={msg.type === "err" ? "err" : "ok"}>{msg.text}</p>}
        <button className="link"
                onClick={() => setMode(mode === "signin" ? "signup" : "signin")}>
          {mode === "signin" ? "Need an account? Sign up" : "Have an account? Sign in"}
        </button>
      </div>
    </div>
  );
}
