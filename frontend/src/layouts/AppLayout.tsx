import { NavLink, Outlet } from "react-router-dom";
import {
  Activity,
  Bot,
  CheckSquare,
  ClipboardList,
  FileSpreadsheet,
  LayoutDashboard,
  MessageCircle,
  Settings,
  Wallet,
  Scale,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { VoiceDock } from "@/components/VoiceDock";

const links = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/invoices", label: "Invoices", icon: FileSpreadsheet },
  { to: "/reconciliation", label: "Reconciliation", icon: Scale },
  { to: "/collections", label: "Collections", icon: Wallet },
  { to: "/ai", label: "AI Teammate", icon: Bot },
  { to: "/approvals", label: "Approvals", icon: CheckSquare },
  { to: "/whatsapp", label: "WhatsApp mock", icon: MessageCircle },
  { to: "/activity", label: "Activity Log", icon: Activity },
  { to: "/evaluation", label: "Evaluation", icon: ClipboardList },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function AppLayout() {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[260px_1fr]">
      <aside className="border-b border-[var(--line)] bg-[#10251f] text-[#e8f2ee] lg:border-b-0 lg:border-r">
        <div className="px-5 py-6">
          <p className="text-xs uppercase tracking-[0.2em] text-teal-200/80">Paytm Build for India</p>
          <h1 className="font-display mt-2 text-3xl leading-none">Vyapar AI</h1>
          <p className="mt-2 text-sm text-teal-100/70">Autonomous receivables teammate</p>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-4 lg:flex-col">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded-xl px-3 py-2 text-sm whitespace-nowrap transition",
                  isActive ? "bg-white/12 text-white" : "text-teal-100/75 hover:bg-white/6 hover:text-white"
                )
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="relative px-4 py-6 pb-28 sm:px-8">
        <Outlet />
        <VoiceDock />
      </main>
    </div>
  );
}
