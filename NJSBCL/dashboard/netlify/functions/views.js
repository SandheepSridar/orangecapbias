const ACCOUNT_ID = 'f3222acd94f0684c3532816365a56fd3';
const SITE_TAG = '6f1263160947431591a298b268b9328f';

exports.handler = async function () {
  const token = process.env.CF_API_TOKEN;
  if (!token) {
    return { statusCode: 500, body: JSON.stringify({ error: 'CF_API_TOKEN not set' }) };
  }

  const now = new Date();
  const since = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
  const query = `
    query {
      viewer {
        accounts(filter: { accountTag: "${ACCOUNT_ID}" }) {
          rumPageloadEventsAdaptiveGroups(
            limit: 1
            filter: { siteTag: "${SITE_TAG}", datetime_geq: "${since.toISOString()}", datetime_leq: "${now.toISOString()}" }
          ) {
            count
          }
        }
      }
    }
  `;

  const res = await fetch('https://api.cloudflare.com/client/v4/graphql', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query }),
  });

  const json = await res.json();
  const groups = json && json.data && json.data.viewer && json.data.viewer.accounts && json.data.viewer.accounts[0]
    ? json.data.viewer.accounts[0].rumPageloadEventsAdaptiveGroups
    : null;

  if (!groups) {
    return { statusCode: 502, body: JSON.stringify({ error: 'Unexpected response from Cloudflare', raw: json }) };
  }

  const views = groups.reduce((sum, g) => sum + (g.count || 0), 0);

  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=300',
    },
    body: JSON.stringify({ views }),
  };
};
