import { createRouter, createWebHistory } from 'vue-router'

import ReportsView from '../views/reports/ReportsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/reports',
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
