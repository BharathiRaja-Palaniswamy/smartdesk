/* The widget's stand-in brain: canned replies, until the SmartDesk API exists.
   Same shape the real one will have:
     business(key)          -> { name, greeting, suggestions } or null
     reply(text, business)  -> Promise<string>
   The real business() asks the server, which also checks the key is used on
   the business's own website; here a key is just looked up in a list. */

window.SmartDeskBrain = (() => {
  const BUSINESSES = {
    pub_demo_sample: {
      name: "Sample Business",
      greeting: "Hi! I'm Sample Business's assistant. I can answer questions and help you book. What can I do for you?",
      suggestions: ["What are your prices?", "Book a massage", "Opening hours"],
    },
  };

  // Keyword -> reply. Clearly a demo: the real brain answers from the
  // business's confirmed knowledge and books through its calendar.
  const REPLIES = [
    [/price|cost|how much/i, "A 60-minute Swedish massage is $80 and a signature facial is $85. (Demo reply)"],
    [/book|appointment|massage|facial/i, "I'd be glad to help you book. Which day and time suit you? (Demo reply: booking connects when the SmartDesk engine is live.)"],
    [/hour|open|close/i, "We're open Monday to Saturday, 9 am to 7 pm, and closed on Sunday. (Demo reply)"],
    [/person|human|staff|call me/i, "Of course. I'll ask the team to call you back. (Demo reply)"],
    [/cancel/i, "I can help you cancel. If someone on our waitlist wants your slot, they'll be offered it. (Demo reply)"],
  ];

  return {
    business(key) {
      return BUSINESSES[key] || null;
    },
    reply(text) {
      const match = REPLIES.find(([pattern]) => pattern.test(text));
      const answer = match ? match[1] : "I'm a demo for now, so I can only answer about prices, booking, hours and cancelling.";
      return new Promise((resolve) => setTimeout(() => resolve(answer), 600));
    },
  };
})();
