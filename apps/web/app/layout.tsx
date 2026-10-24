import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BioNexus AI",
  description: "Evidence-grounded biomedical research intelligence",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="light" data-scroll-behavior="smooth" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: `try{var t=localStorage.getItem('bionexus-theme'),r=document.documentElement;if(t==='dark')r.setAttribute('data-theme','dark');else if(t==='system')r.removeAttribute('data-theme')}catch(e){}` }} />
      </head>
      <body>
        <a className="skip" href="#content">Skip to content</a>
        {children}
      </body>
    </html>
  );
}
