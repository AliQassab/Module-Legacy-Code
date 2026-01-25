import {apiService} from "../lib/api.mjs";

const createBloom = (template, bloom) => {
  if (!bloom) return;
  const bloomFrag = document.getElementById(template).content.cloneNode(true);
  const bloomParser = new DOMParser();

  const bloomArticle = bloomFrag.querySelector("[data-bloom]");
  const bloomUsername = bloomFrag.querySelector("[data-username]");
  const bloomTime = bloomFrag.querySelector("[data-time]");
  const bloomTimeLink = bloomFrag.querySelector("a:has(> [data-time])");
  const bloomContent = bloomFrag.querySelector("[data-content]");
  const rebloomHeader = bloomFrag.querySelector("[data-rebloom-header]");
  const rebloomIndicator = bloomFrag.querySelector("[data-rebloom-indicator]");
  const rebloomBtn = bloomFrag.querySelector("[data-rebloom-btn]");
  const rebloomCount = bloomFrag.querySelector("[data-rebloom-count]");

  bloomArticle.setAttribute("data-bloom-id", bloom.id);
  bloomUsername.setAttribute("href", `/profile/${bloom.sender}`);
  bloomUsername.textContent = bloom.sender;
  bloomTime.textContent = _formatTimestamp(bloom.sent_timestamp);
  bloomTimeLink.setAttribute("href", `/bloom/${bloom.id}`);
  bloomContent.replaceChildren(
    ...bloomParser.parseFromString(_formatHashtags(bloom.content), "text/html")
      .body.childNodes
  );

  if (bloom.rebloomer && bloom.original_sender) {
    rebloomHeader.style.display = "block";
    rebloomIndicator.textContent = `${bloom.sender} rebloomed ${bloom.original_sender}`;
    bloomArticle.classList.add("bloom--rebloomed");
  }

  if (bloom.rebloom_count > 0) {
    rebloomCount.style.display = "inline";
    rebloomCount.textContent = `${bloom.rebloom_count} rebloom${bloom.rebloom_count !== 1 ? 's' : ''}`;
  }

  if (rebloomBtn) {
    rebloomBtn.addEventListener("click", () => handleRebloom(bloom.id));
  }

  return bloomFrag;
};

async function handleRebloom(bloomId) {
  await apiService.rebloom(bloomId);
}

function _formatHashtags(text) {
  if (!text) return text;
  return text.replace(
    /\B#[^#]+/g,
    (match) => `<a href="/hashtag/${match.slice(1)}">${match}</a>`
  );
}

function _formatTimestamp(timestamp) {
  if (!timestamp) return "";

  try {
    const date = new Date(timestamp);
    const now = new Date();
    const diffSeconds = Math.floor((now - date) / 1000);

    // Less than a minute
    if (diffSeconds < 60) {
      return `${diffSeconds}s`;
    }

    // Less than an hour
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) {
      return `${diffMinutes}m`;
    }

    // Less than a day
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) {
      return `${diffHours}h`;
    }

    // Less than a week
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) {
      return `${diffDays}d`;
    }

    // Format as month and day for older dates
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
    }).format(date);
  } catch (error) {
    console.error("Failed to format timestamp:", error);
    return "";
  }
}

export {createBloom};
