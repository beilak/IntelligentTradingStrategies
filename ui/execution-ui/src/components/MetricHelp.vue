<script setup lang="ts">
import { CircleHelp, X } from "lucide-vue-next";
import { onBeforeUnmount, ref, useId, watch } from "vue";
import type { PnlMetricHelp } from "../pnlHelp";

const props = defineProps<{
  help: PnlMetricHelp;
}>();

const isOpen = ref(false);
const dialogId = useId();

watch(isOpen, (value) => {
  if (value) document.addEventListener("keydown", onKeydown);
  else document.removeEventListener("keydown", onKeydown);
});

onBeforeUnmount(() => document.removeEventListener("keydown", onKeydown));

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") isOpen.value = false;
}
</script>

<template>
  <button
    class="metric-help-button"
    type="button"
    :aria-label="`Что означает «${help.title}»`"
    :aria-controls="dialogId"
    :aria-expanded="isOpen"
    :title="`Что означает «${help.title}»`"
    @click.stop="isOpen = true"
  >
    <CircleHelp :size="14" />
  </button>

  <Teleport to="body">
    <div v-if="isOpen" class="metric-help-backdrop" @click.self="isOpen = false">
      <section :id="dialogId" class="metric-help-dialog" role="dialog" aria-modal="true" :aria-label="help.title">
        <header>
          <div>
            <span>Справка по показателю</span>
            <strong>{{ help.title }}</strong>
          </div>
          <button class="icon-button" type="button" title="Закрыть" aria-label="Закрыть" @click="isOpen = false">
            <X :size="17" />
          </button>
        </header>
        <div class="metric-help-content">
          <article>
            <span>Что означает</span>
            <p>{{ help.meaning }}</p>
          </article>
          <article>
            <span>Как считается в ITS</span>
            <p class="metric-help-formula">{{ help.calculation }}</p>
          </article>
          <article>
            <span>Как читать</span>
            <p>{{ help.interpretation }}</p>
          </article>
          <article v-if="help.caveat" class="metric-help-caveat">
            <span>Важно</span>
            <p>{{ help.caveat }}</p>
          </article>
        </div>
      </section>
    </div>
  </Teleport>
</template>
