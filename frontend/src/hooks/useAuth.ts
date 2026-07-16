"use client";
import { useState, useCallback, useEffect } from "react";
import { api } from "@/services/api";

export function useAuth() {
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("token");
    const storedEmail = localStorage.getItem("email");
    if (stored) setToken(stored);
    if (storedEmail) setEmail(storedEmail);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.auth.login(email, password);
    localStorage.setItem("token", res.access_token);
    localStorage.setItem("email", email);
    setToken(res.access_token);
    setEmail(email);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const res = await api.auth.register(email, password);
    localStorage.setItem("token", res.access_token);
    localStorage.setItem("email", email);
    setToken(res.access_token);
    setEmail(email);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    localStorage.removeItem("email");
    setToken(null);
    setEmail(null);
  }, []);

  return { token, email, isAuthenticated: !!token, login, register, logout };
}
