const state = {
  token: localStorage.getItem("token") || "",
  
  setToken(t) {
    if (!t || t === "undefined" || t === "null") return;
    this.token = t;
    localStorage.setItem("token", t);
    // Clear stale session expiry data on new token
    localStorage.removeItem('session_expiry_user');
    localStorage.removeItem('session_expiry_admin');
    window.dispatchEvent(new CustomEvent("auth:changed"));
  },
  
  clearToken() {
    this.token = "";
    localStorage.removeItem("token");
    try {
      localStorage.removeItem('resume_feedback');
      localStorage.removeItem('resume_filename');
      localStorage.removeItem('target_job_title');
      localStorage.removeItem('session_expiry_user');
      localStorage.removeItem('session_expiry_admin');
      localStorage.removeItem('interview_voice_gender');
      // Clear all items to be absolutely sure no session data leaks
      // but we might want to keep some non-sensitive settings if any.
      // For now, let's be explicit with the sensitive ones.
    } catch (e) {
      console.error("Error clearing localStorage:", e);
    }
    window.dispatchEvent(new CustomEvent("auth:changed"));
  }
};

if (state.token === "undefined" || state.token === "null") {
  state.clearToken();
}

document.addEventListener("htmx:configRequest", function (evt) {
  if (state.token) evt.detail.headers["Authorization"] = "Bearer " + state.token;
});

document.addEventListener("htmx:responseError", function (evt) {
  if (evt.detail.xhr.status === 401) {
    state.clearToken();
    if (window.location.pathname !== '/' && !window.location.pathname.includes('login.html') && !window.location.pathname.includes('register.html') && !window.location.pathname.includes('cta.html')) {
        const is_admin_page = window.location.pathname.includes('admin');
        window.location.href = is_admin_page ? '/static/pages/admin.html' : '/static/pages/login.html';
    }
  }
});

function logout() {
  state.clearToken();
  window.location.href = "/";
}

function decodeToken(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
      return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
}

window.icp = { state, logout, decodeToken };

// Global Loader Logic
const hideLoader = () => {
  const loader = document.getElementById("global-loader");
  if (loader) {
    loader.classList.add("fade-out");
    setTimeout(() => loader.remove(), 500);
  }
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", hideLoader);
} else {
  hideLoader();
}
