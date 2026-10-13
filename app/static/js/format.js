// Pure formatting helpers. No DOM access, so they can be unit tested outside a browser.

export const format = {
  fullName: (patient) => `${patient.first_name} ${patient.last_name}`,
  initials: (patient) => (patient.first_name[0] + patient.last_name[0]).toUpperCase(),
  phone: (digits) => (/^\d{10}$/.test(digits || "")
    ? `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}` : digits || ""),
  percent: (part, whole) => (whole ? `${Math.round((part / whole) * 100)}%` : "0%"),
  count: (number, singular, plural) => `${number.toLocaleString()} ${number === 1 ? singular : plural || singular + "s"}`,
  age(dateOfBirth) {
    const [month, day, year] = dateOfBirth.split("/").map(Number);
    const today = new Date();
    let years = today.getFullYear() - year;
    if (today.getMonth() + 1 < month || (today.getMonth() + 1 === month && today.getDate() < day)) years -= 1;
    return years < 1 ? "Under 1 year old" : `${years} years old`;
  },
  // The year is left out for dates in the current year, to keep table columns narrow.
  date(timestamp) {
    const date = new Date(timestamp);
    const sameYear = date.getFullYear() === new Date().getFullYear();
    return date.toLocaleDateString([], { year: sameYear ? undefined : "numeric", month: "short", day: "numeric" });
  },
  dateTime: (timestamp) => new Date(timestamp).toLocaleString([], {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  }),
  ago(timestamp) {
    const minutes = Math.max(0, Math.round((Date.now() - new Date(timestamp).getTime()) / 60000));
    if (minutes < 1) return "Just now";
    if (minutes < 60) return `${minutes} min ago`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `${hours} ${hours === 1 ? "hour" : "hours"} ago`;
    const days = Math.round(hours / 24);
    return `${days} ${days === 1 ? "day" : "days"} ago`;
  },
  endReason(reason) {
    const known = {
      "assistant-said-end-call-phrase": "Agent ended the call",
      "assistant-ended-call": "Agent ended the call",
      "customer-ended-call": "Caller hung up",
      "silence-timed-out": "Silence timeout",
      "exceeded-max-duration": "Reached time limit",
    };
    if (!reason) return "Not reported";
    return known[reason] || reason.replace(/[-.]/g, " ");
  },
  // Vapi transcripts are plain text, one "AI: ..." or "User: ..." turn per line.
  turns(transcript) {
    const turns = [];
    for (const line of (transcript || "").split("\n")) {
      const match = line.match(/^(AI|User):\s*(.*)$/);
      if (match) turns.push({ agent: match[1] === "AI", text: match[2] });
      else if (line.trim() && turns.length) turns[turns.length - 1].text += " " + line.trim();
      else if (line.trim()) turns.push({ agent: true, text: line.trim() });
    }
    return turns;
  },
};
