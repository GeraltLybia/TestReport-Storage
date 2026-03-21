import { createRouter, createWebHistory } from 'vue-router'

import DashboardView from '../views/reports/DashboardView.vue'
import ReportsView from '../views/reports/ReportsView.vue'

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
      component: DashboardView,
    },
    {
      path: '/reports',
      name: 'reports',
      component: ReportsView,
    },
    {
      path: '/reports/:reportId',
      name: 'report-by-id',
      component: ReportsView,
    },
  ],
})

export default router
