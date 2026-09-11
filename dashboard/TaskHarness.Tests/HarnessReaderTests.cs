using TaskHarness.Core;

namespace TaskHarness.Tests;

public class HarnessReaderTests
{
    [Fact]
    public void ResolveSource_prefers_nested_harness()
    {
        var root = Directory.CreateTempSubdirectory("th-");
        try
        {
            var nested = Directory.CreateDirectory(Path.Combine(root.FullName, ".harness"));
            File.WriteAllText(Path.Combine(nested.FullName, "tasks.json"), """{"project":"p","rev":1,"tasks":[]}""");
            Assert.Equal(nested.FullName, HarnessReader.ResolveSource(root.FullName));
        }
        finally { root.Delete(true); }
    }

    [Fact]
    public void ResolveSource_keeps_root_tasks_json()
    {
        var root = Directory.CreateTempSubdirectory("th-");
        try
        {
            File.WriteAllText(Path.Combine(root.FullName, "tasks.json"), """{"project":"p","rev":1,"tasks":[]}""");
            Assert.Equal(root.FullName, HarnessReader.ResolveSource(root.FullName));
        }
        finally { root.Delete(true); }
    }

    [Fact]
    public void Parse_rejects_unknown_status()
    {
        var ex = Assert.Throws<InvalidDataException>(() => HarnessReader.Parse(new Dictionary<string, string>
        {
            ["tasks.json"] = """{"tasks":[{"id":"a","status":"nope"}]}"""
        }));
        Assert.Contains("未知状态", ex.Message);
    }

    [Fact]
    public void Parse_rejects_bad_jsonl_but_optional_board_can_be_bad()
    {
        Assert.Throws<InvalidDataException>(() => HarnessReader.Parse(new Dictionary<string, string>
        {
            ["tasks.json"] = """{"tasks":[{"id":"a","status":"pending"}]}""",
            ["reviews.jsonl"] = "[]"
        }));
        var snap = HarnessReader.Parse(new Dictionary<string, string>
        {
            ["tasks.json"] = """{"project":"demo","rev":1,"tasks":[{"id":"a","status":"pending","desc":"x","priority":1}]}""",
            ["board.json"] = "{bad"
        });
        Assert.Null(snap.Board);
        Assert.Equal("demo", snap.Tasks.Project);
    }

    [Fact]
    public void Load_reads_optional_files()
    {
        var root = Directory.CreateTempSubdirectory("th-");
        try
        {
            var h = Directory.CreateDirectory(Path.Combine(root.FullName, ".harness"));
            File.WriteAllText(Path.Combine(h.FullName, "tasks.json"), """{"project":"p","rev":2,"tasks":[{"id":"t1","status":"active","desc":"do","priority":1}]}""");
            File.WriteAllText(Path.Combine(h.FullName, "progress.txt"), "hello");
            var snap = HarnessReader.Load(root.FullName);
            Assert.Equal(h.FullName, snap.Path);
            Assert.Equal("t1", snap.Tasks.Tasks[0].Id);
            Assert.Equal("hello", snap.Progress);
        }
        finally { root.Delete(true); }
    }

    [Fact]
    public void ProbeCandidates_dedupes_cwd_and_exe()
    {
        var root = Directory.CreateTempSubdirectory("th-");
        try
        {
            var got = HarnessReader.ProbeCandidates(root.FullName, root.FullName).ToArray();
            Assert.Single(got);
            Assert.Equal(Path.GetFullPath(root.FullName), got[0]);
        }
        finally { root.Delete(true); }
    }
}
