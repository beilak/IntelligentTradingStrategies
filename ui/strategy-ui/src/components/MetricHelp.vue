<script setup lang="ts">
import { CircleHelp, X } from "lucide-vue-next";
import { onBeforeUnmount, ref, useId, watch } from "vue";
import type { PnlMetricHelp } from "../backtestPnlHelp";
import type { Locale } from "../types";

const props = defineProps<{
    help: PnlMetricHelp;
    locale: Locale;
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
        :aria-label="`${locale === 'ru' ? 'Что означает' : 'What does'} «${help.title}»`"
        :aria-controls="dialogId"
        :aria-expanded="isOpen"
        :title="`${locale === 'ru' ? 'Что означает' : 'What does'} «${help.title}»`"
        @click.stop="isOpen = true"
    >
        <CircleHelp :size="14" />
    </button>

    <Teleport to="body">
        <div
            v-if="isOpen"
            class="metric-help-backdrop"
            @click.self="isOpen = false"
        >
            <section
                :id="dialogId"
                class="metric-help-dialog"
                role="dialog"
                aria-modal="true"
                :aria-label="help.title"
            >
                <header>
                    <div>
                        <span>{{
                            locale === "ru"
                                ? "Справка по показателю"
                                : "Metric reference"
                        }}</span>
                        <strong>{{ help.title }}</strong>
                    </div>
                    <button
                        class="metric-help-close"
                        type="button"
                        :title="locale === 'ru' ? 'Закрыть' : 'Close'"
                        :aria-label="locale === 'ru' ? 'Закрыть' : 'Close'"
                        @click="isOpen = false"
                    >
                        <X :size="17" />
                    </button>
                </header>
                <div class="metric-help-content">
                    <article>
                        <span>{{
                            locale === "ru" ? "Что означает" : "Meaning"
                        }}</span>
                        <p>{{ help.meaning }}</p>
                    </article>
                    <article>
                        <span>{{
                            locale === "ru"
                                ? "Как считается в ITS"
                                : "ITS calculation"
                        }}</span>
                        <p class="metric-help-formula">
                            {{ help.calculation }}
                        </p>
                    </article>
                    <article>
                        <span>{{
                            locale === "ru" ? "Как читать" : "Interpretation"
                        }}</span>
                        <p>{{ help.interpretation }}</p>
                    </article>
                    <article v-if="help.caveat" class="metric-help-caveat">
                        <span>{{
                            locale === "ru" ? "Важно" : "Important"
                        }}</span>
                        <p>{{ help.caveat }}</p>
                    </article>
                </div>
            </section>
        </div>
    </Teleport>
</template>

<style scoped>
.metric-help-button {
    align-items: center;
    background: rgba(102, 217, 239, 0.08);
    border: 1px solid rgba(102, 217, 239, 0.28);
    border-radius: 999px;
    color: #8de5f5;
    cursor: pointer;
    display: inline-flex;
    flex: 0 0 auto;
    height: 20px;
    justify-content: center;
    padding: 0;
    transition: 120ms ease;
    width: 20px;
}

.metric-help-button:hover,
.metric-help-button:focus-visible {
    background: rgba(102, 217, 239, 0.17);
    border-color: rgba(102, 217, 239, 0.62);
    color: #d4f8ff;
    outline: none;
}

.metric-help-backdrop {
    align-items: center;
    background: rgba(5, 7, 11, 0.82);
    display: flex;
    inset: 0;
    justify-content: center;
    padding: 18px;
    position: fixed;
    z-index: 300;
}

.metric-help-dialog {
    background: #11141b;
    border: 1px solid #344158;
    border-radius: 10px;
    box-shadow: 0 28px 90px rgba(0, 0, 0, 0.62);
    color: #f4f6fb;
    max-height: calc(100vh - 36px);
    max-width: 650px;
    overflow: auto;
    width: min(650px, calc(100vw - 36px));
}

.metric-help-dialog > header {
    align-items: center;
    border-bottom: 1px solid #2b3342;
    display: flex;
    justify-content: space-between;
    min-height: 66px;
    padding: 12px 14px;
}

.metric-help-dialog > header > div {
    display: grid;
    gap: 4px;
}

.metric-help-dialog > header span,
.metric-help-content article > span {
    color: #8992a3;
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.metric-help-dialog > header strong {
    font-size: 18px;
}

.metric-help-close {
    align-items: center;
    background: #151821;
    border: 1px solid #2b3342;
    border-radius: 8px;
    color: #66d9ef;
    cursor: pointer;
    display: inline-flex;
    height: 38px;
    justify-content: center;
    width: 38px;
}

.metric-help-content {
    display: grid;
}

.metric-help-content article {
    display: grid;
    gap: 7px;
    padding: 13px 15px;
}

.metric-help-content article + article {
    border-top: 1px solid #252b36;
}

.metric-help-content p {
    color: #d6dbe5;
    font-size: 13px;
    line-height: 1.55;
    margin: 0;
    white-space: pre-line;
}

.metric-help-content .metric-help-formula {
    background: rgba(102, 217, 239, 0.06);
    border: 1px solid rgba(102, 217, 239, 0.18);
    border-radius: 7px;
    color: #c8f5fd;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    padding: 10px 11px;
}

.metric-help-content .metric-help-caveat {
    background: rgba(255, 204, 102, 0.06);
}

.metric-help-content .metric-help-caveat > span,
.metric-help-content .metric-help-caveat p {
    color: #ffe4a3;
}
</style>
