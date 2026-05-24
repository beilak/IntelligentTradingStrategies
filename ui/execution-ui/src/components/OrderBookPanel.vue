<script setup lang="ts">
import type { OrderBookLevel, OrderBookSnapshot } from "../types";

const props = defineProps<{
  snapshot: OrderBookSnapshot | null;
  status: "idle" | "connecting" | "live" | "stale" | "error";
  error: string;
}>();

const maxQuantity = () => {
  const rows = [...(props.snapshot?.asks ?? []), ...(props.snapshot?.bids ?? [])];
  return Math.max(1, ...rows.map((row) => Number(row.quantity ?? 0)));
};

function width(row: OrderBookLevel): string {
  return `${Math.max(4, (Number(row.quantity ?? 0) / maxQuantity()) * 100)}%`;
}

function formatNumber(value: number | null | undefined, digits = 4): string {
  if (!Number.isFinite(value ?? NaN)) return "n/a";
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: digits }).format(Number(value));
}

function formatTime(value?: string | null): string {
  if (!value) return "n/a";
  return new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}
</script>

<template>
  <div class="orderbook-shell">
    <div class="orderbook-status" :class="status">
      <span>{{ status }}</span>
      <strong>{{ snapshot ? formatTime(snapshot.time) : "n/a" }}</strong>
    </div>

    <div v-if="error" class="orderbook-error">{{ error }}</div>

    <div class="spread-line">
      <span>Best ask</span>
      <strong>{{ formatNumber(snapshot?.asks?.[0]?.price) }}</strong>
      <span>Best bid</span>
      <strong>{{ formatNumber(snapshot?.bids?.[0]?.price) }}</strong>
    </div>

    <div class="orderbook-grid">
      <section>
        <header>
          <span>Продажа</span>
          <small>price / volume</small>
        </header>
        <div class="book-rows asks">
          <div v-for="row in snapshot?.asks ?? []" :key="`ask-${row.price}-${row.quantity}`" class="book-row">
            <div class="depth-bar" :style="{ width: width(row) }"></div>
            <strong>{{ formatNumber(row.price) }}</strong>
            <span>{{ formatNumber(row.quantity, 0) }}</span>
          </div>
          <div v-if="!snapshot?.asks?.length" class="book-empty">Нет данных</div>
        </div>
      </section>

      <section>
        <header>
          <span>Покупка</span>
          <small>price / volume</small>
        </header>
        <div class="book-rows bids">
          <div v-for="row in snapshot?.bids ?? []" :key="`bid-${row.price}-${row.quantity}`" class="book-row">
            <div class="depth-bar" :style="{ width: width(row) }"></div>
            <strong>{{ formatNumber(row.price) }}</strong>
            <span>{{ formatNumber(row.quantity, 0) }}</span>
          </div>
          <div v-if="!snapshot?.bids?.length" class="book-empty">Нет данных</div>
        </div>
      </section>
    </div>
  </div>
</template>
