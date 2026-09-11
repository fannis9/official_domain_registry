import { createRouter, createWebHistory } from "vue-router";
import { tokenStore } from "../api.js";

const routes = [
  { path: "/", name: "home", component: () => import("../views/HomeView.vue") },
  { path: "/domains", name: "domains", component: () => import("../views/DomainsView.vue") },
  { path: "/login", name: "login", component: () => import("../views/LoginView.vue") },
  { path: "/register", name: "register", component: () => import("../views/RegisterView.vue") },
  { path: "/submitted", name: "submitted", component: () => import("../views/SubmittedView.vue") },
  { path: "/me", name: "me", component: () => import("../views/MeView.vue"), meta: { auth: true } },
  { path: "/admin/login", name: "admin-login", component: () => import("../views/admin/AdminLogin.vue") },
  { path: "/admin", name: "admin-queue", component: () => import("../views/admin/AdminQueue.vue"), meta: { admin: true } },
  { path: "/admin/orgs", name: "admin-orgs", component: () => import("../views/admin/AdminOrgs.vue"), meta: { admin: true } },
  { path: "/admin/users", name: "admin-users", component: () => import("../views/admin/AdminUsers.vue"), meta: { admin: true } },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  if (to.meta.auth && !tokenStore.access) {
    return { name: "login", query: { next: to.fullPath } };
  }
  if (to.meta.admin && !tokenStore.admin) {
    return { name: "admin-login" };
  }
  return true;
});

export default router;
