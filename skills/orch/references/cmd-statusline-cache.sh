# Keep Command Code's rate limits for the orch board. Insert after LIM5 and LIM7.
if [ -n "$LIM5" ] || [ -n "$LIM7" ]; then
  cache_dir="${ORCH_USAGE_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/orch}"
  mkdir -p "$cache_dir" 2>/dev/null && \
  cache_tmp=$(mktemp "$cache_dir/usage-cmd.json.XXXXXX" 2>/dev/null) && \
  printf '%s' "$input" | jq -c '{cli: "cmd", fetched_at: (now | floor), model: .model.display_name, rate_limits: .rate_limits}' \
    > "$cache_tmp" 2>/dev/null && mv -f "$cache_tmp" "$cache_dir/usage-cmd.json" 2>/dev/null
fi
