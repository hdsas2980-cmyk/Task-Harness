namespace TaskHarness.Core;

public static class HarnessLogic
{
    public static IReadOnlyList<TaskItem> Eligible(IEnumerable<TaskItem> all)
    {
        var list = all.ToList();
        var byId = list.ToDictionary(t => t.Id, StringComparer.Ordinal);
        return list
            .Where(t => t.Status is HarnessStatus.Pending or HarnessStatus.Regressed)
            .Where(t => t.Deps.All(d => byId.TryGetValue(d, out var dep) && dep.Status == HarnessStatus.Passed))
            .OrderBy(t => t.Priority ?? 999999)
            .ToList();
    }

    public static string Gate(TaskItem task, HarnessSnapshot model)
    {
        if (task.Status != HarnessStatus.Passed) return "";
        var review = model.Reviews.LastOrDefault(r => r.Str("task") == task.Id);
        if (review is null) return "门禁缺口：缺成功证据或独立评审";
        var evId = review.Str("ev");
        var evidence = model.Evidence.FirstOrDefault(e =>
            e.Str("task") == task.Id && e.Str("id") is { } id && id == evId);
        var verdict = review.Str("verdict");
        var ctx = review.Str("reviewer_context");
        var exit = evidence?.El("exit");
        var exitOk = exit is not null && exit.Value.ValueKind == System.Text.Json.JsonValueKind.Number && exit.Value.GetInt32() == 0;
        return verdict == "pass" && !string.IsNullOrWhiteSpace(ctx) && exitOk
            ? "已关联记录，独立性须人工核验"
            : "门禁缺口：缺成功证据或独立评审";
    }

    public static IReadOnlyList<TaskItem> Filter(
        IEnumerable<TaskItem> all,
        string filter,
        string search,
        string sortBy)
    {
        var list = all.ToList();
        var readyIds = new HashSet<string>(Eligible(list).Select(t => t.Id), StringComparer.Ordinal);
        var q = (search ?? "").Trim().ToLowerInvariant();
        var rows = list.Where(t =>
        {
            if (filter == "eligible" && !readyIds.Contains(t.Id)) return false;
            if (filter is not ("all" or "eligible") && t.Status != filter) return false;
            if (q.Length == 0) return true;
            var blob = (t.Id + " " + t.DisplayDesc + " " + (t.Verify ?? "") + " " + t.Status).ToLowerInvariant();
            return blob.Contains(q);
        }).ToList();

        rows.Sort((a, b) => sortBy switch
        {
            "id" => string.Compare(a.Id, b.Id, StringComparison.Ordinal),
            "status" => Array.IndexOf(HarnessStatus.All, a.Status).CompareTo(Array.IndexOf(HarnessStatus.All, b.Status)),
            _ => (a.Priority ?? 999999).CompareTo(b.Priority ?? 999999)
        });
        return rows;
    }
}
