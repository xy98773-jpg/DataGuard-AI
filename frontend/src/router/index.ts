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
  ],
})

export default router
