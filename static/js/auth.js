(function () {
    const currentUrl = new URL(window.location.href);
    if (currentUrl.searchParams.has('_tt_auth_recovery')) {
        currentUrl.searchParams.delete('_tt_auth_recovery');
        window.history.replaceState(window.history.state, '', currentUrl.pathname + currentUrl.search + currentUrl.hash);
    }

    const originalFetch = window.fetch.bind(window);
    window.fetch = async function (input, options) {
        let url;
        try {
            url = new URL(typeof input === 'string' || input instanceof URL ? input : input.url, window.location.href);
        } catch (error) {
            return originalFetch(input, options);
        }
        if (url.origin !== window.location.origin || !url.pathname.startsWith('/api/')) {
            return originalFetch(input, options);
        }

        const response = await originalFetch(input, { ...options, redirect: 'manual' });
        if (response.status === 401 || response.type === 'opaqueredirect') {
            const notice = document.getElementById('auth-session-notice');
            const link = document.getElementById('auth-session-login');
            if (notice && link) {
                const destination = new URL(window.location.href);
                destination.searchParams.set('_tt_auth_recovery', 'login');
                const login = new URL('/.auth/login/aad', window.location.origin);
                login.searchParams.set('post_login_redirect_uri', destination.pathname + destination.search);
                link.href = login.pathname + login.search;
                notice.hidden = false;
            }
        }
        return response;
    };
}());