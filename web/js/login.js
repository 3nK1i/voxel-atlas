(() => {
  "use strict";

  const form = document.getElementById("loginForm");
  const usernameInput = document.getElementById("username");
  const passwordInput = document.getElementById("password");
  const passwordToggle = document.getElementById("passwordToggle");
  const submitButton = document.getElementById("loginSubmit");
  const submitLabel = document.getElementById("loginSubmitLabel");
  const message = document.getElementById("loginMessage");
  const brandmark = document.getElementById("loginBrandmark");
  const logo = document.getElementById("loginLogo");

  const setMessage = (text = "") => {
    message.textContent = text;
  };

  const setBusy = (busy) => {
    submitButton.disabled = busy;
    usernameInput.disabled = busy;
    passwordInput.disabled = busy;
    submitLabel.textContent = busy ? "Signing in…" : "Login";
  };

  const redirectToWorkspace = () => {
    window.location.replace("/workspace");
  };

  const checkCurrentSession = async () => {
    try {
      const response = await fetch("/api/auth/session", {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      if (payload.authenticated === true) {
        redirectToWorkspace();
      }
    } catch (_error) {
      // The login form remains usable if the preflight session check is unavailable.
    }
  };

  passwordToggle.addEventListener("click", () => {
    const showing = passwordInput.type === "text";
    passwordInput.type = showing ? "password" : "text";
    passwordToggle.setAttribute("aria-pressed", String(!showing));
    passwordToggle.setAttribute("aria-label", showing ? "Show password" : "Hide password");
    passwordInput.focus({ preventScroll: true });
  });

  logo.addEventListener("error", () => {
    brandmark.classList.add("is-missing");
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setMessage();

    const username = usernameInput.value.trim();
    const password = passwordInput.value;
    if (!username || !password) {
      setMessage("Enter your username and password.");
      (!username ? usernameInput : passwordInput).focus();
      return;
    }

    setBusy(true);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      if (response.ok) {
        redirectToWorkspace();
        return;
      }

      if (response.status === 401) {
        setMessage("Invalid username or password.");
      } else if (response.status === 503) {
        setMessage("Authentication is not configured for this environment.");
      } else {
        setMessage("Unable to sign in. Please try again.");
      }
    } catch (_error) {
      setMessage("Unable to reach VoxelAtlas. Check the server and try again.");
    } finally {
      setBusy(false);
    }
  });

  checkCurrentSession();
})();
