import type { Metadata } from "next";
import { Sora } from "next/font/google";
import "./globals.css";

const sora = Sora({
  variable: "--font-sora",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "VoyageMind — AI Travel Planning Workspace",
  description:
    "Plan trips with an AI copilot: itinerary builder, budget analytics, live weather & maps, contingency planning and what-if simulations.",
};

// Applies the saved (or system) theme before first paint to avoid flashing.
const themeInit = `try{var t=localStorage.getItem('vm-theme');var d=t?t==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.classList.toggle('dark',d);}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${sora.variable} h-full`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
