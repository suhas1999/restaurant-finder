// Gatekeeper between the public website and GitHub Actions.
// Holds the GitHub token (secret GH_TOKEN) so the page never sees it, and enforces:
// valid town names, no duplicates, one run at a time, and DAILY_LIMIT new towns per 24 hours.

const WORKFLOW = "add-town.yml";

export default {
  async fetch(request, env) {
    const cors = {
      "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN,
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };
    const reply = (body, status = 200) =>
      new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });

    const gh = (path, init = {}) =>
      fetch(`https://api.github.com/repos/${env.REPO}${path}`, {
        ...init,
        headers: {
          Authorization: `Bearer ${env.GH_TOKEN}`,
          Accept: "application/vnd.github+json",
          "User-Agent": "restaurant-finder-worker",
          ...(init.headers || {}),
        },
      });
    const recentRuns = async () =>
      (await (await gh(`/actions/workflows/${WORKFLOW}/runs?per_page=30`)).json()).workflow_runs || [];

    const url = new URL(request.url);
    try {
      if (request.method === "POST" && url.pathname === "/add") {
        const { town: raw = "" } = await request.json();
        if (!/^[A-Za-z][A-Za-z .'-]{1,39}$/.test(raw.trim()))
          return reply({ error: "Please type just the town name in English letters, e.g. Tanuku" }, 400);
        const town = raw.trim().split(/\s+/).map(w => w[0].toUpperCase() + w.slice(1).toLowerCase()).join(" ");
        const slug = town.replace(/ /g, "_").toLowerCase();

        const towns = await (await fetch(`${env.SITE_URL}/towns.json`, { cf: { cacheTtl: 0 } })).json().catch(() => []);
        if (towns.some(t => t.slug === slug)) return reply({ exists: true, town, slug });

        const runs = await recentRuns();
        const active = runs.find(r => r.status !== "completed");
        if (active) {
          if (active.display_title === `Add ${town}`) return reply({ started: true, town, slug });
          return reply({ error: `Busy adding ${active.display_title.slice(4)}. Please try again in a few minutes.` }, 409);
        }
        const dayAgo = Date.now() - 24 * 3600 * 1000;
        const today = runs.filter(r => Date.parse(r.created_at) > dayAgo).length;
        if (today >= Number(env.DAILY_LIMIT))
          return reply({ error: `Daily limit of ${env.DAILY_LIMIT} new towns reached. Please try again tomorrow.` }, 429);

        const res = await gh(`/actions/workflows/${WORKFLOW}/dispatches`, {
          method: "POST",
          body: JSON.stringify({ ref: "main", inputs: { town } }),
        });
        if (res.status !== 204) return reply({ error: "Could not start the search. Please try later." }, 502);
        return reply({ started: true, town, slug });
      }

      if (request.method === "GET" && url.pathname === "/status") {
        const town = url.searchParams.get("town") || "";
        const run = (await recentRuns()).find(r => r.display_title === `Add ${town}`);
        if (!run) return reply({ status: "queued", steps: [] });
        const jobs = (await (await gh(`/actions/runs/${run.id}/jobs`)).json()).jobs || [];
        const steps = (jobs[0]?.steps || [])
          .filter(s => !/^(Set up job|Post |Complete job)/.test(s.name))
          .map(s => ({ name: s.name, status: s.status, conclusion: s.conclusion }));
        return reply({ status: run.status, conclusion: run.conclusion, started: run.run_started_at, steps });
      }

      return reply({ error: "Not found" }, 404);
    } catch (e) {
      return reply({ error: "Something went wrong. Please try again." }, 500);
    }
  },
};
