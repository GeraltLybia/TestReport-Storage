<script setup lang="ts">
import AppSidebar from '../components/common/layout/AppSidebar.vue'
</script>

<template>
  <div class="main-layout">
    <AppSidebar />
    <div class="main-layout-content">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.main-layout {
  min-height: 100vh;
  display: flex;
}

.main-layout-content {
  flex: 1;
  min-width: 0;
}

@media (max-width: 900px) {
  .main-layout {
    flex-direction: column;
  }
}
</style>
