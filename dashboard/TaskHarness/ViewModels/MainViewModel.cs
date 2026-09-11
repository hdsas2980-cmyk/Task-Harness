using System.Collections.ObjectModel;
using System.IO;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using TaskHarness.Core;

namespace TaskHarness.App.ViewModels;

public partial class FilterItem : ObservableObject
{
    public string Id { get; init; } = "all";
    public string Title { get; init; } = "";
    public string Hint { get; init; } = "";
    [ObservableProperty] private int _count;
    [ObservableProperty] private bool _isSelected;
}

public sealed class TaskRow
{
    public int Index { get; init; }
    public TaskItem Task { get; init; } = new();
    public string StatusLabel { get; init; } = "";
    public string Gate { get; init; } = "";
    public string Deps { get; init; } = "—";
    public double Fill { get; init; }
}

public sealed class EventRow
{
    public string Kind { get; init; } = "";
    public string Task { get; init; } = "";
    public string Detail { get; init; } = "";
    public string Ts { get; init; } = "";
}

public partial class MainViewModel : ObservableObject
{
    static readonly string LastDirFile = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "TaskHarness", "last-dir.txt");

    HarnessSnapshot _model = new();
    bool _rebuilding;

    public MainViewModel()
    {
        Filters = new ObservableCollection<FilterItem>
        {
            new() { Id = "blocked", Title = "已阻塞", Hint = "卡住了，先解开" },
            new() { Id = "evidence_ready", Title = "待评审", Hint = "验过才算完成" },
            new() { Id = "active", Title = "进行中", Hint = "正在做，还没交" },
            new() { Id = "eligible", Title = "可推进", Hint = "现在就能开工" },
            new() { Id = "all", Title = "全部任务", Hint = "不筛选，看全集", IsSelected = true },
        };
        SortOptions = new[] { "priority", "status", "id" };
    }

    public Func<string?>? PickFolder { get; set; }

    public ObservableCollection<FilterItem> Filters { get; }
    public ObservableCollection<TaskRow> Rows { get; } = new();
    public ObservableCollection<EventRow> Events { get; } = new();
    public IReadOnlyList<string> SortOptions { get; }

    [ObservableProperty] private string _windowTitle = "长任务看板";
    [ObservableProperty] private string _projectPath = "未选择目录";
    [ObservableProperty] private string _projectName = "—";
    [ObservableProperty] private string _projectRev = "rev —";
    [ObservableProperty] private string _statusText = "选择项目任务目录（载入任务 / L）";
    [ObservableProperty] private bool _statusIsError;
    [ObservableProperty] private string _filter = "all";
    [ObservableProperty] private string _sortBy = "priority";
    [ObservableProperty] private string _search = "";
    [ObservableProperty] private string _tab = "next";
    [ObservableProperty] private int _tabIndex;
    [ObservableProperty] private int _selectedIndex;
    [ObservableProperty] private string _heroId = "—";
    [ObservableProperty] private string _heroDesc = "尚未编排任务";
    [ObservableProperty] private string _heroMeta = "—";
    [ObservableProperty] private string _heroCmd = "";
    [ObservableProperty] private string _detail = "没有选中任务";
    [ObservableProperty] private string _progress = "";
    [ObservableProperty] private string _mapWhere = "";
    [ObservableProperty] private string _mapNext = "";
    [ObservableProperty] private bool _hasMap;
    [ObservableProperty] private string _sourceHint = "只读，不写任务真相源";
    [ObservableProperty] private int _countAll;
    [ObservableProperty] private int _countEligible;

    partial void OnFilterChanged(string value) => Rebuild();
    partial void OnSortByChanged(string value) => Rebuild();
    partial void OnSearchChanged(string value) => Rebuild();
    partial void OnSelectedIndexChanged(int value)
    {
        if (_rebuilding) return;
        UpdateDetail();
    }
    partial void OnTabIndexChanged(int value)
    {
        Tab = value switch
        {
            1 => "tasks",
            2 => "timeline",
            3 => "log",
            _ => "next"
        };
    }

    public void Boot()
    {
        var last = ReadLastDir();
        var exeDir = Path.GetDirectoryName(Environment.ProcessPath) ?? AppContext.BaseDirectory;
        var extras = last is null ? Array.Empty<string>() : new[] { last };
        foreach (var path in HarnessReader.ProbeCandidates(Environment.CurrentDirectory, exeDir).Concat(extras))
        {
            if (!HarnessReader.HasTasks(path)) continue;
            try
            {
                LoadFrom(path, "已载入");
                return;
            }
            catch
            {
                if (path == last) WriteLastDir(null);
            }
        }
        StatusText = "当前目录没有任务，点「载入任务」选择项目任务目录";
        StatusIsError = false;
    }

    [RelayCommand]
    void Load()
    {
        if (PickFolder is null) return;
        StatusText = "正在选择项目任务目录…";
        StatusIsError = false;
        var picked = PickFolder();
        if (string.IsNullOrWhiteSpace(picked))
        {
            StatusText = "已取消选择目录";
            return;
        }
        try { LoadFrom(picked, "已载入"); }
        catch (Exception ex)
        {
            StatusText = "读取失败：" + ex.Message;
            StatusIsError = true;
        }
    }

    [RelayCommand]
    void Refresh()
    {
        if (string.IsNullOrWhiteSpace(_model.Path) || !Directory.Exists(_model.Path))
        {
            StatusText = "尚未选择项目任务目录";
            StatusIsError = true;
            return;
        }
        try { LoadFrom(_model.Path, "已刷新"); }
        catch (Exception ex)
        {
            StatusText = "刷新失败：" + ex.Message + "，已保留上次任务";
            StatusIsError = true;
        }
    }

    [RelayCommand]
    void CopyVerify()
    {
        if (string.IsNullOrWhiteSpace(HeroCmd)) return;
        try
        {
            Clipboard.SetText(HeroCmd);
            StatusText = "已复制验证命令";
            StatusIsError = false;
        }
        catch (Exception ex)
        {
            StatusText = "复制失败：" + ex.Message;
            StatusIsError = true;
        }
    }

    [RelayCommand]
    void SetFilter(string id)
    {
        if (string.IsNullOrWhiteSpace(id)) return;
        Filter = id;
    }

    [RelayCommand]
    void SetTab(string id)
    {
        TabIndex = id switch
        {
            "tasks" => 1,
            "timeline" => 2,
            "log" => 3,
            _ => 0
        };
    }

    public void LoadFrom(string path, string verb)
    {
        var snap = HarnessReader.Load(path);
        _model = snap;
        WriteLastDir(snap.Path);
        ProjectPath = snap.Path;
        SourceHint = "只读 · " + snap.Path;
        Rebuild();
        StatusText = verb + " " + snap.Path + " · " + DateTime.Now.ToString("T");
        StatusIsError = false;
    }

    void Rebuild()
    {
        if (_rebuilding) return;
        _rebuilding = true;
        try
        {
            var all = _model.Tasks.Tasks;
            var ready = HarnessLogic.Eligible(all);
            CountAll = all.Count;
            CountEligible = ready.Count;
            foreach (var f in Filters)
            {
                f.Count = f.Id switch
                {
                    "all" => all.Count,
                    "eligible" => ready.Count,
                    _ => all.Count(t => t.Status == f.Id)
                };
                f.IsSelected = f.Id == Filter;
            }

            ProjectName = string.IsNullOrWhiteSpace(_model.Tasks.Project) ? "未命名项目" : _model.Tasks.Project!;
            ProjectRev = "rev " + (_model.Tasks.Rev?.ToString() ?? "—");
            WindowTitle = "长任务看板 — " + ProjectName;

            var next = ready.FirstOrDefault();
            HeroId = next?.Id ?? "—";
            HeroDesc = next is null
                ? (all.Count == 0 ? "尚未编排任务" : "没有可推进任务（依赖未全部通过）")
                : next.DisplayDesc;
            if (next is null) HeroMeta = "—";
            else
            {
                var done = next.Deps.Count(d => all.Any(t => t.Id == d && t.Status == HarnessStatus.Passed));
                HeroMeta = (next.Deps.Count == 0 ? "无前置依赖" : $"依赖 {done}/{next.Deps.Count} 已通过")
                           + "  ·  优先级 " + (next.Priority?.ToString() ?? "—");
            }
            HeroCmd = next?.Verify ?? "";

            HasMap = _model.Board is not null;
            MapWhere = _model.Board?.Where ?? "";
            MapNext = _model.Board is null ? "" : string.Join("\n", _model.Board.Next.Select(n =>
                n.Task + " —— " + (n.Why ?? "未写") + (string.IsNullOrWhiteSpace(n.See) ? "" : "（做完会看到：" + n.See + "）")));

            var rows = HarnessLogic.Filter(all, Filter, Search, SortBy);
            var keep = SelectedIndex;
            if (keep >= rows.Count) keep = Math.Max(0, rows.Count - 1);
            Rows.Clear();
            for (var i = 0; i < rows.Count; i++)
            {
                var t = rows[i];
                Rows.Add(new TaskRow
                {
                    Index = i,
                    Task = t,
                    StatusLabel = HarnessStatus.Labels[t.Status],
                    Gate = HarnessLogic.Gate(t, _model),
                    Deps = t.Deps.Count == 0 ? "无依赖" : string.Join("、", t.Deps),
                    Fill = HarnessStatus.Fill[t.Status]
                });
            }
            SelectedIndex = rows.Count == 0 ? -1 : keep;
            UpdateDetail();
            Progress = string.IsNullOrWhiteSpace(_model.Progress) ? "暂无进度日志" : _model.Progress;
        }
        finally
        {
            _rebuilding = false;
        }
    }

    void UpdateDetail()
    {
        var all = _model.Tasks.Tasks;
        var rows = HarnessLogic.Filter(all, Filter, Search, SortBy);
        var selected = SelectedIndex;
        var current = selected >= 0 && selected < rows.Count ? rows[selected] : null;
        if (current is null) Detail = "没有选中任务";
        else
        {
            var g = HarnessLogic.Gate(current, _model);
            Detail = current.Id + "\n"
                     + HarnessStatus.Labels[current.Status] + " · 优先级 " + (current.Priority?.ToString() ?? "—") + "\n"
                     + current.DisplayDesc + "\n"
                     + "依赖 " + (current.Deps.Count == 0 ? "无" : string.Join("、", current.Deps)) + "\n"
                     + (string.IsNullOrWhiteSpace(current.ReasonText) ? "" : "阻塞原因：" + current.ReasonText + "\n")
                     + (current.Verify ?? "未写验证") + "\n"
                     + (string.IsNullOrWhiteSpace(g) ? "无门禁缺口" : g);
        }

        Events.Clear();
        var mixed = _model.Evidence.Select(x => new { Kind = "证据", Row = x })
            .Concat(_model.Reviews.Select(x => new { Kind = "评审", Row = x }))
            .OrderByDescending(x => x.Row.Str("ts") ?? "")
            .Take(8);
        foreach (var item in mixed)
        {
            var verdict = item.Row.Str("verdict");
            var detail = item.Kind == "证据"
                ? "退出码 " + (item.Row.El("exit")?.ToString() ?? "未知")
                : ((verdict == "pass" ? "通过" : verdict == "fail" ? "评审未通过" : verdict ?? "未知")
                   + " · " + (item.Row.Str("reviewer_context") ?? "未记录上下文"));
            Events.Add(new EventRow
            {
                Kind = item.Kind,
                Task = item.Row.Str("task") ?? "—",
                Detail = detail,
                Ts = item.Row.Str("ts") ?? "未记录时间"
            });
        }
    }

    static string? ReadLastDir()
    {
        try { return File.Exists(LastDirFile) ? File.ReadAllText(LastDirFile).Trim() : null; }
        catch { return null; }
    }

    static void WriteLastDir(string? path)
    {
        try
        {
            var dir = Path.GetDirectoryName(LastDirFile);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            if (string.IsNullOrWhiteSpace(path)) File.Delete(LastDirFile);
            else File.WriteAllText(LastDirFile, path);
        }
        catch { /* last-dir is convenience only */ }
    }
}
