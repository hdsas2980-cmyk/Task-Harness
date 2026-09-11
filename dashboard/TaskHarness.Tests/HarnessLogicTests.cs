using TaskHarness.Core;

namespace TaskHarness.Tests;

public class HarnessLogicTests
{
    static TaskItem T(string id, string status, int? pri = null, params string[] deps) => new()
    {
        Id = id,
        Status = status,
        Priority = pri,
        DependsOn = deps.Length == 0 ? null : deps.ToList()
    };

    [Fact]
    public void Eligible_requires_pending_or_regressed_and_passed_deps()
    {
        var all = new[]
        {
            T("a", HarnessStatus.Passed, 1),
            T("b", HarnessStatus.Pending, 2, "a"),
            T("c", HarnessStatus.Pending, 1, "missing"),
            T("d", HarnessStatus.Active, 1),
            T("e", HarnessStatus.Regressed, 3)
        };
        var got = HarnessLogic.Eligible(all).Select(x => x.Id).ToArray();
        Assert.Equal(new[] { "b", "e" }, got);
    }

    [Fact]
    public void Gate_passed_without_review_is_gap()
    {
        var task = T("a", HarnessStatus.Passed);
        var snap = HarnessReader.Parse(new Dictionary<string, string>
        {
            ["tasks.json"] = """{"tasks":[{"id":"a","status":"passed"}]}"""
        });
        Assert.Equal("门禁缺口：缺成功证据或独立评审", HarnessLogic.Gate(task, snap));
    }

    [Fact]
    public void Filter_eligible_and_search()
    {
        var all = new[]
        {
            T("keep", HarnessStatus.Pending, 1),
            T("skip", HarnessStatus.Active, 1)
        };
        all[0].Desc = "alpha";
        var rows = HarnessLogic.Filter(all, "eligible", "alp", "priority");
        Assert.Single(rows);
        Assert.Equal("keep", rows[0].Id);
    }
}
