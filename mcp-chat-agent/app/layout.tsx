import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'MCP Chat Agent',
  description: 'Created with v0',
  generator: 'v0.dev',
  authors: [{ name: 'Pratik' }],
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
