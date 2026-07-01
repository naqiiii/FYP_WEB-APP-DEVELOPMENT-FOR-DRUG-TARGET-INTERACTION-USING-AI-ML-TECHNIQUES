'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { useRouter, usePathname } from 'next/navigation';
import { updateProfile } from '@/services/api-client';

export default function Navbar() {
    const { isAuthenticated, user, logout, updateUser } = useAuth();
    const router = useRouter();
    const pathname = usePathname();

    const [dropdownOpen, setDropdownOpen] = useState(false);
    const dropdownRef = useRef(null);
    const fileInputRef = useRef(null);
    const [uploading, setUploading] = useState(false);

    // Auto-close the user menu when clicking anywhere else on the page
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setDropdownOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleLogout = () => {
        logout();
        setDropdownOpen(false);
        router.push('/login');
    };

    const handlePhotoUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        setUploading(true);

        try {
            const reader = new FileReader();

            reader.onload = (e) => {
                const img = new window.Image();

                img.onload = async () => {
                    const canvas = document.createElement('canvas');
                    const MAX = 250;

                    let w = img.width;
                    let h = img.height;

                    if (w > h) {
                        if (w > MAX) {
                            h *= MAX / w;
                            w = MAX;
                        }
                    } else {
                        if (h > MAX) {
                            w *= MAX / h;
                            h = MAX;
                        }
                    }

                    canvas.width = w;
                    canvas.height = h;

                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, w, h);

                    const base64 = canvas.toDataURL('image/jpeg', 0.85);

                    try {
                        const newUser = await updateProfile({
                            profile_picture: base64
                        });

                        updateUser(newUser);
                    } catch (err) {
                        console.error('Profile update failed:', err);
                    } finally {
                        setUploading(false);
                    }
                };

                img.src = e.target.result;
            };

            reader.readAsDataURL(file);
        } catch (err) {
            console.error('Image processing error:', err);
            setUploading(false);
        }
    };

    const isActive = (path) => pathname === path;

    const navLinkClass = (path) => `
        relative px-1 text-sm font-medium tracking-wide transition-colors duration-200
        ${
            isActive(path)
                ? 'text-primary after:content-[""] after:absolute after:-bottom-[20px] after:left-0 after:w-full after:h-[2px] after:bg-primary after:rounded-full'
                : 'text-muted-foreground hover:text-primary'
        }
    `;

    // Show first two letters of username if no profile pic exists
    const userInitials = user?.username
        ? user.username.substring(0, 2).toUpperCase()
        : 'US';

    return (
        <>
            <nav className="sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-md transition-colors duration-300">
                <div className="max-w-6xl mx-auto px-6">
                    <div className="flex justify-between items-center h-16">

                        <Link href="/" className="flex items-center gap-3 group">
                            <div className="w-10 h-10 rounded-xl border border-primary/20 bg-background shadow-sm p-1 flex items-center justify-center group-hover:border-primary/40 group-hover:shadow-md transition-all">
                                <img
                                    src="/logo3.svg"
                                    alt="DTI Logo"
                                    className="w-full h-full object-contain"
                                />
                            </div>

                            <span className="text-lg font-bold tracking-wide text-foreground group-hover:text-primary transition-colors hidden sm:block mt-0.5">
                                DTI Engine
                            </span>
                        </Link>

                        <div className="flex items-center gap-5">
                            <div className="h-4 w-px bg-border hidden sm:block"></div>

                            {isAuthenticated ? (
                                <>
                                    <Link href="/" className={navLinkClass('/')}>
                                        Home
                                    </Link>

                                    <Link href="/dashboard" className={navLinkClass('/dashboard')}>
                                        Predict
                                    </Link>

                                    <Link href="/history" className={navLinkClass('/history')}>
                                        History
                                    </Link>

                                    <Link href="/about" className={navLinkClass('/about')}>
                                        About
                                    </Link>

                                    <div className="relative ml-2" ref={dropdownRef}>
                                        <button
                                            onClick={() => setDropdownOpen(!dropdownOpen)}
                                            className="flex items-center justify-center w-9 h-9 rounded-full bg-gradient-to-tr from-primary to-green-600 text-white font-bold text-sm shadow-sm ring-2 ring-transparent transition-all hover:ring-primary/40 overflow-hidden"
                                        >
                                            {user?.profile_picture ? (
                                                <img
                                                    src={user.profile_picture}
                                                    alt="Profile"
                                                    className="w-full h-full object-cover"
                                                />
                                            ) : (
                                                userInitials
                                            )}
                                        </button>

                                        {dropdownOpen && (
                                            <div className="absolute right-0 mt-3 w-48 rounded-xl bg-card border border-border shadow-xl overflow-hidden py-1 animate-fade-in origin-top-right z-50">
                                                <div className="px-4 py-3 border-b border-border">
                                                    <p className="text-sm font-semibold text-foreground">
                                                        {user?.username || 'Researcher'}
                                                    </p>

                                                    <p className="text-xs text-muted-foreground truncate">
                                                        {user?.email || 'user@example.com'}
                                                    </p>
                                                </div>

                                                <div className="py-1">
                                                    <button
                                                        onClick={() => fileInputRef.current?.click()}
                                                        disabled={uploading}
                                                        className="w-full text-left px-4 py-2 text-sm text-foreground hover:bg-secondary transition-colors"
                                                    >
                                                        {uploading ? 'Uploading...' : 'Change Photo'}
                                                    </button>
                                                </div>

                                                <div className="border-t border-border py-1">
                                                    <button
                                                        onClick={handleLogout}
                                                        className="w-full text-left px-4 py-2 text-sm text-destructive hover:bg-destructive/10 transition-colors"
                                                    >
                                                        Log out
                                                    </button>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </>
                            ) : (
                                <>
                                    <Link href="/" className={navLinkClass('/')}>
                                        Home
                                    </Link>

                                    <Link href="/about" className={navLinkClass('/about')}>
                                        About
                                    </Link>

                                    <span className="text-border hidden sm:block">·</span>

                                    <Link
                                        href="/login"
                                        className="text-sm font-semibold tracking-wide text-foreground hover:text-primary transition-colors"
                                    >
                                        Sign In
                                    </Link>

                                    <Link
                                        href="/signup"
                                        className="btn-premium px-4 h-9 shadow-md shadow-primary/20"
                                    >
                                        Get Started
                                    </Link>
                                </>
                            )}

                            <input
                                type="file"
                                accept="image/*"
                                ref={fileInputRef}
                                onChange={handlePhotoUpload}
                                className="hidden"
                            />
                        </div>
                    </div>
                </div>
            </nav>
        </>
    );
}