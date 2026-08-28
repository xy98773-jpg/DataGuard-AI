import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('../views/Dashboard.vue'),
    },
    {
      path: '/workflow',
      name: 'workflow',
      component: () => import('../views/Workflow.vue'),
    },
    {
      path: '/issues',
      name: 'issues',
      component: () => import('../views/Issues.vue'),
    },
    {
      path: '/approval',
      name: 'approval',
      component: () => import('../views/Approval.vue'),
    },
    {
      path: '/datasource',
      name: 'datasource',
      component: () => import('../views/DataSource.vue'),    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/Settings.vue'),
    },
    {
      path: '/system',
      name: 'system',
      component: () => import('../views/SystemStatus.vue'),
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/Login.vue'),
    },
  ],
})

// 路由守卫：未登录访问业务页 → 跳转登录页（登录后跳回）
router.beforeEach((to) => {
  const token = localStorage.getItem('dg_token')
  if (to.name !== 'login' && !token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && token) {
    return { name: 'dashboard' }
  }
  return true
})

export default router
