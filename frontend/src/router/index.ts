import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('../views/reports/DashboardView.vue'),
    },
    {
      path: '/reports',
      name: 'reports',
      component: () => import('../views/reports/ReportsView.vue'),
    },
    {
      path: '/reports/:reportId',
      name: 'report-by-id',
      component: () => import('../views/reports/ReportsView.vue'),
    },
    {
      path: '/runs',
      name: 'runs',
      component: () => import('../views/runs/RunsView.vue'),
    },
    {
      path: '/runs/:runId',
      name: 'run-by-id',
      component: () => import('../views/runs/RunsView.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/dashboard',
    },
  ],
})

export default router
