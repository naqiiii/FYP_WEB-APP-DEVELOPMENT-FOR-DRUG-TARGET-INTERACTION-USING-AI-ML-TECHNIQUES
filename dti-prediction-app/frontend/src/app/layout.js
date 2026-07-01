/*Root Layout with Navbar and Footer*/

import { Inter } from 'next/font/google';
import './globals.css';
import { AuthProvider } from '@/context/AuthContext';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata = {
    title: 'DTI Interface Engine',
    description: 'Advanced Drug-Target Interaction Prediction Platform',
};

export default function RootLayout({ children }) {
    return (
        <html lang="en" className={inter.variable}>
            <body className="font-sans antialiased min-h-screen flex flex-col bg-background text-foreground selection:bg-primary/30 selection:text-white transition-colors duration-300">
                <AuthProvider>
                    {children}
                </AuthProvider>
            </body>
        </html>
    );
}
