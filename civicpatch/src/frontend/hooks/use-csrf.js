import { useState, useEffect } from "haunted";

export function useCsrf() {
  const [csrf, setCsrf] = useState(getCsrfCookie());

  useEffect(() => {
    function checkCsrf() {
      setCsrf(getCsrfCookie());
    }
    window.addEventListener("focus", checkCsrf);
    return () => window.removeEventListener("focus", checkCsrf);
  }, []);

  console.log("Current CSRF token:", csrf);
  return csrf;
}

function getCsrfCookie() {
  const name = 'csrf_token=';
  const parts = document.cookie.split(';');
  for (let i = 0; i < parts.length; i++) {
    let c = parts[i].trim();
    if (c.indexOf(name) === 0) return decodeURIComponent(c.substring(name.length));
  }
  return '';
}