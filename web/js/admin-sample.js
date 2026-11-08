/* Sample businesses for the admin console preview (docs/features/admin-console.md).
   Made-up names and numbers: the real list comes from the registry's health
   summaries, never from a business's content. */

window.ADMIN_SAMPLE = [
  { name: "Test Studio", type: "Spa", status: "live", since: "7 Nov",
    channels: { widget: "teststudio.example", phone: true, calendar: 6 },
    services: 24, priceMissing: 2, chats: 132, bookings: 18, handoffs: 3, lastChat: "2 h ago",
    errors: 0, p95: 6.2, cost: 0.42, budget: 5 },
  { name: "Sample Salon", type: "Salon", status: "draft", since: "",
    channels: { widget: "", phone: false, calendar: 0 },
    services: 11, priceMissing: 0, chats: 0, bookings: 0, handoffs: 0, lastChat: "never",
    errors: 0, p95: null, cost: 0.03, budget: 5 },
  { name: "Example Clinic", type: "Clinic", status: "failed", since: "",
    channels: { widget: "exampleclinic.example", phone: false, calendar: 0 }, failure: "Go live: calendar not shared",
    services: 9, priceMissing: 1, chats: 0, bookings: 0, handoffs: 0, lastChat: "never",
    errors: 0, p95: null, cost: 0.05, budget: 5 },
  { name: "Demo Barbers", type: "Barber", status: "paused", since: "2 Nov",
    channels: { widget: "demobarbers.example", phone: true, calendar: 3 },
    services: 7, priceMissing: 0, chats: 41, bookings: 9, handoffs: 1, lastChat: "1 day ago",
    errors: 4, p95: 12.4, cost: 1.10, budget: 5 },
];
