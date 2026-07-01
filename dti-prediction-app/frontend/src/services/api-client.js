import axios from 'axios';

// Central API client; every helper below goes through the same auth handling.
// This means the app has one place to add tokens to requests and refresh them automatically.
const apiClient = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL || '',
    headers: {
        'Content-Type': 'application/json',
    },
});

apiClient.interceptors.request.use(
    (config) => {
        // Attach the saved access token to every API request automatically.
        if (typeof window !== 'undefined') {
            const token = localStorage.getItem('token');
            if (token) {
                config.headers.Authorization = `Bearer ${token}`;
            }
        }
        return config;
    },
    (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        // If the backend says the token has expired, try refreshing it once.
        // This keeps the user logged in as long as the refresh token is still valid.
        if (error.response?.status === 401 && !originalRequest._retry && !originalRequest.url.includes('/api/auth/login')) {
            originalRequest._retry = true;

            if (typeof window !== 'undefined') {
                const refreshToken = localStorage.getItem('refresh_token');
                if (refreshToken) {
                    try {
                        const res = await axios.post(`${apiClient.defaults.baseURL}/api/auth/refresh`, {
                            refresh_token: refreshToken
                        });

                        if (res.data.access_token) {
                            localStorage.setItem('token', res.data.access_token);
                            originalRequest.headers.Authorization = `Bearer ${res.data.access_token}`;
                            return apiClient(originalRequest);
                        }
                    } catch (refreshErr) {
                        console.error('Session expired. Please log in again.');
                    }
                }

                // Clear local state only after refresh has failed or no refresh token exists.
                localStorage.clear();
                if (!window.location.pathname.includes('/login')) {
                    window.location.href = '/login';
                }
            }
        }
        return Promise.reject(error);
    }
);

export default apiClient;

/**
 * Sign up a new user
 */
export async function signup(email, password, fullName) {
    const clientUrl = typeof window !== 'undefined' ? window.location.origin : undefined;
    const response = await apiClient.post('/api/auth/signup', {
        email,
        password,
        full_name: fullName,
        client_url: clientUrl,
    });
    return response.data;
}

/**
 * Login user and get JWT token
 */
export async function login(email, password) {
    const response = await apiClient.post('/api/auth/login', {
        email,
        password,
    });
    return response.data;
}

/**
 * Log the user out and clear session
 */
export async function logout() {
    try {
        await apiClient.post('/api/auth/logout');
    } catch (e) {
        console.error('Backend logout failed', e);
    }
}

/**
 * Update the current user's profile information
 */
export async function updateProfile(profileData) {
    const response = await apiClient.put('/api/auth/profile', profileData);
    return response.data;
}

/**
 * Verify user email address via token
 */
export async function verifyEmail(token) {
    const response = await apiClient.get('/api/auth/verify-email', {
        params: { token },
    });
    return response.data;
}

/**
 * Forgot password request
 */
export async function forgotPassword(email) {
    const clientUrl = typeof window !== 'undefined' ? window.location.origin : undefined;
    const response = await apiClient.post('/api/auth/forgot-password', {
        email,
        client_url: clientUrl,
    });
    return response.data;
}

/**
 * Reset password
 */
export async function resetPassword(token, newPassword) {
    const response = await apiClient.post('/api/auth/reset-password', {
        token,
        new_password: newPassword,
    });
    return response.data;
}

/**
 * Make a DTI prediction
 */
export async function predict(drugName, smiles, proteinName, sequence, minAffinityCheckpoint = null) {
    const response = await apiClient.post('/api/predict', {
        drug_name: drugName,
        smiles: smiles,
        protein_name: proteinName,
        sequence: sequence,
        min_affinity_checkpoint: minAffinityCheckpoint
    });
    return response.data;
}

/** Screen many drugs against one protein target. */
export async function predictBatch(drugInputs, proteinName, sequence, minAffinityCheckpoint = null) {
    const response = await apiClient.post('/api/predict/batch', {
        drug_inputs: drugInputs,
        protein_name: proteinName,
        sequence: sequence,
        min_affinity_checkpoint: minAffinityCheckpoint
    });
    return response.data;
}

/** Screen one drug against many protein targets. */
export async function predictProteinBatch(drugName, smiles, proteinInputs, minAffinityCheckpoint = null) {
    const response = await apiClient.post('/api/predict/batch-protein', {
        drug_name: drugName,
        smiles: smiles,
        protein_inputs: proteinInputs,
        min_affinity_checkpoint: minAffinityCheckpoint
    });
    return response.data;
}

/**
 * Get the history of previous predictions
 */
export async function getHistory(limit = 20, skip = 0) {
    const response = await apiClient.get('/api/history', {
        params: { limit, skip },
    });
    return response.data;
}

/** Resolve a protein structure before opening the 3D viewers. */
export async function resolveProteinModel(proteinLabel, proteinSequence) {
    const response = await apiClient.post('/api/visualization/resolve-protein-model', {
        protein_label: proteinLabel || null,
        protein_sequence: proteinSequence || null,
    });
    return response.data;
}

export async function resolveLigandModel(smiles) {
    const response = await apiClient.post('/api/visualization/resolve-ligand-model', {
        smiles,
    });
    return response.data;
}

export async function dockComplex(payload) {
    const response = await apiClient.post('/api/visualization/dock', payload);
    return response.data;
}
