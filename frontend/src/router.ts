import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'overview',
    component: () => import('@/pages/overview/OverviewPage.vue'),
  },
  {
    path: '/policies',
    name: 'policies',
    component: () => import('@/pages/policies/PolicyListPage.vue'),
  },
  {
    path: '/policies/:id',
    name: 'policy-detail',
    component: () => import('@/pages/policies/PolicyDetailPage.vue'),
  },
  {
    path: '/import',
    name: 'import',
    component: () => import('@/pages/import/ImportPage.vue'),
  },
  {
    path: '/import/:jobId',
    name: 'review-job',
    component: () => import('@/pages/import/ReviewJobPage.vue'),
  },
  {
    path: '/ask',
    name: 'ask',
    component: () => import('@/pages/ask/AskPage.vue'),
  },
  {
    path: '/claim',
    name: 'claim',
    component: () => import('@/pages/claim/ClaimSimulatePage.vue'),
  },
  {
    path: '/renewal',
    name: 'renewal',
    component: () => import('@/pages/renewal/RenewalPage.vue'),
  },
  {
    path: '/members',
    name: 'members',
    component: () => import('@/pages/members/MembersPage.vue'),
  },
  {
    path: '/reports',
    name: 'reports',
    component: () => import('@/pages/reports/ReportsPage.vue'),
  },
  {
    path: '/eval',
    name: 'eval',
    component: () => import('@/pages/eval/EvalDashboardPage.vue'),
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/pages/settings/SettingsPage.vue'),
  },
  {
    path: '/dev/styleguide',
    name: 'styleguide',
    component: () => import('@/pages/dev/StyleguidePage.vue'),
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
