import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "MockClaw - AI-Powered Mock API Generator",
  description: "Watch traffic, generate mocks instantly. The ultimate tool for developers.",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased">
        {children}
      </body>
    </html>
  )
}
