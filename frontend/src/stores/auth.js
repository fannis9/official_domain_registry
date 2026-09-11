import { defineStore } from "pinia";
import { tokenStore } from "../api.js";

export const useAuth = defineStore("auth", {
  state: () => ({
    user: tokenStore.user,
  }),
  getters: {
    loggedIn: (s) => !!s.user,
  },
  actions: {
    setSession(data) {
      tokenStore.access = data.access_token;
      tokenStore.refresh = data.refresh_token || "";
      this.user = { username: data.username || "" };
      if (!data.username) {
        import("../api.js").then((m) => {
          m.api("/api/v1/auth/whoami", { auth: true }).then((w) => {
            this.user = { username: w.username, is_admin: w.is_admin };
            tokenStore.user = this.user;
          });
        });
      }
      tokenStore.user = this.user;
    },
    logout() {
      tokenStore.clearUser();
      this.user = null;
    },
  },
});
