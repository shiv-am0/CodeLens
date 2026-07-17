"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Code2,
  LayoutDashboard,
  GitBranch,
  Globe,
  Shield,
  Zap,
  ArrowRight,
  Github,
  Menu,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

const features = [
  {
    icon: Code2,
    title: "AI-Powered Analysis",
    description: "AI analyzes your entire codebase and generates comprehensive documentation.",
  },
  {
    icon: LayoutDashboard,
    title: "Smart Dashboard",
    description: "Architecture, API docs, database schemas, and more in one place.",
  },
  {
    icon: GitBranch,
    title: "Folder Intelligence",
    description: "Every folder explained with purpose, responsibilities, and relationships.",
  },
  {
    icon: Globe,
    title: "Mermaid Diagrams",
    description: "Auto-generated architecture and sequence diagrams.",
  },
  {
    icon: Shield,
    title: "Staff Engineer Chat",
    description: "Ask any question and get answers like a senior engineer who built the project.",
  },
  {
    icon: Zap,
    title: "Lightning Fast",
    description: "Background processing with real-time progress updates.",
  },
];

export default function LandingPage() {
  const [repoUrl, setRepoUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mobileMenu, setMobileMenu] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl.trim()) {
      setError("Please enter a GitHub repository URL");
      return;
    }
    if (!repoUrl.includes("github.com")) {
      setError("Please enter a valid GitHub URL");
      return;
    }
    setLoading(true);
    setError("");

    try {
      const { api } = await import("@/services/api");
      const repo = await api.repositories.analyze(repoUrl.trim());
      router.push(`/dashboard?id=${repo.id}`);
    } catch (err: any) {
      setError(err.message || "Failed to analyze repository");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-950">
      <header className="fixed top-0 left-0 right-0 z-50 glass border-b border-surface-800/50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
              <Code2 className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-semibold text-surface-100">CodeLens</span>
          </div>

          <nav className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-surface-400 hover:text-surface-100 transition-colors text-sm">Features</a>
            <a
              href="https://github.com/shiv-am0/CodeLens"
              target="_blank"
              rel="noopener noreferrer"
              className="text-surface-400 hover:text-surface-100 transition-colors"
            >
              <Github className="w-5 h-5" />
            </a>
          </nav>

          <button
            onClick={() => setMobileMenu(!mobileMenu)}
            className="md:hidden text-surface-400"
          >
            {mobileMenu ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </header>

      <main>
        <section className="pt-32 pb-20 px-6">
          <div className="max-w-4xl mx-auto text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
            >
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent/10 border border-accent/20 text-accent text-sm mb-8">
                <Zap className="w-4 h-4" />
                AI-Powered Code Intelligence
              </div>

              <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6">
                <span className="text-gradient">
                  Understand Any Codebase
                </span>
                <br />
                <span className="text-surface-100">in Minutes</span>
              </h1>

              <p className="text-lg md:text-xl text-surface-400 max-w-2xl mx-auto mb-12 leading-relaxed">
                Paste any public GitHub repository and instantly receive AI-generated
                documentation, architecture diagrams, onboarding guidance, and intelligent answers.
              </p>
            </motion.div>

            <motion.form
              onSubmit={handleSubmit}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="max-w-2xl mx-auto"
            >
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1 relative">
                  <Github className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-500" />
                  <input
                    type="text"
                    value={repoUrl}
                    onChange={(e) => { setRepoUrl(e.target.value); setError(""); }}
                    placeholder="https://github.com/owner/repository"
                    className="input-field pl-12 h-14 text-base"
                  />
                </div>
                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary h-14 px-8 text-base flex items-center gap-2 whitespace-nowrap"
                >
                  {loading ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <>
                      Analyze <ArrowRight className="w-5 h-5" />
                    </>
                  )}
                </button>
              </div>
              {error && (
                <p className="mt-3 text-sm text-red-400">{error}</p>
              )}
            </motion.form>

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.4 }}
              className="mt-8 flex items-center justify-center gap-6 text-sm text-surface-500"
            >
              <span>No sign-up required</span>
              <span className="w-1 h-1 rounded-full bg-surface-700" />
              <span>Public repos only</span>
              <span className="w-1 h-1 rounded-full bg-surface-700" />
              <span>100MB max</span>
            </motion.div>
          </div>
        </section>

        <section id="features" className="py-20 px-6">
          <div className="max-w-6xl mx-auto">
            <motion.div
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              className="text-center mb-16"
            >
              <h2 className="text-3xl md:text-4xl font-bold text-surface-100 mb-4">
                Everything you need to understand any project
              </h2>
              <p className="text-surface-400 text-lg max-w-2xl mx-auto">
                From architecture diagrams to intelligent chat — CodeLens gives you
                a complete understanding of any codebase.
              </p>
            </motion.div>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {features.map((feature, i) => (
                <motion.div
                  key={feature.title}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="card-gradient rounded-2xl p-6 hover:border-accent/30 transition-all duration-300 group"
                >
                  <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center mb-4 group-hover:bg-accent/20 transition-colors">
                    <feature.icon className="w-6 h-6 text-accent" />
                  </div>
                  <h3 className="text-lg font-semibold text-surface-100 mb-2">{feature.title}</h3>
                  <p className="text-surface-400 leading-relaxed">{feature.description}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-surface-800 py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-surface-400 text-sm">
            <Code2 className="w-4 h-4" />
            CodeLens — Understand Any Codebase in Minutes
          </div>
          <div className="flex items-center gap-6 text-surface-500 text-sm">
            <span>Built with Next.js, FastAPI & OpenAI</span>
          </div>
        </div>
      </footer>

      {loading && (
        <div className="fixed inset-0 z-50 bg-surface-950/80 backdrop-blur-sm flex items-center justify-center">
          <div className="text-center max-w-md">
            <Loader2 className="w-12 h-12 text-accent animate-spin mx-auto mb-6" />
            <h3 className="text-xl font-semibold text-surface-100 mb-3">
              Analyzing Repository
            </h3>
            <p className="text-surface-400 text-sm break-all bg-surface-900/50 rounded-lg px-4 py-2 border border-surface-800">
              {repoUrl}
            </p>
            <p className="text-surface-500 text-sm mt-4">
              Cloning, indexing, and running AI analysis...
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
