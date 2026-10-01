<script setup lang="ts">
import ReportsDashboard from '../../components/common/reports/ReportsDashboard.vue'
import { useReports } from '../../composables/useReports'

const { reports, selectedReportId } = useReports()
</script>

<template>
  <div class="dashboard-view">
    <ReportsDashboard :reports="reports" :selected-report-id="selectedReportId" />
  </div>
</template>

<style scoped src="../../assets/style/views/reports/DashboardView.css"></style>
