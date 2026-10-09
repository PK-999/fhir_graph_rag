import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FHIRGraph Dashboard",
  description: "Synthetic healthcare knowledge-graph platform",
};

import { Sidebar } from "@/components/Sidebar";
import { ThemeProvider } from "@/components/ThemeProvider";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex h-full flex-row overflow-hidden bg-background text-foreground transition-colors duration-500 selection:bg-blue-500/30">
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange={false}
        >
          <Sidebar />
          <main className="flex-1 flex flex-col h-full overflow-y-auto bg-muted/30">
            <div className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-2.5 text-center text-sm font-medium text-amber-700 dark:text-amber-500 sticky top-0 z-50 backdrop-blur-xl shadow-sm">
              Synthetically Generated Health Data — For Demonstration Only
            </div>
            <div className="flex-1 p-6 md:p-10 max-w-7xl mx-auto w-full">
              {children}
            </div>
          </main>
        </ThemeProvider>
      </body>
    </html>
  );
}
