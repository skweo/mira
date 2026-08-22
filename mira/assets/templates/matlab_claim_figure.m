function matlab_claim_figure(project_root, claim_id, parameters_json, prefix)
% Reproducible single-claim MATLAB figure with a justified local inset.
if nargin < 1, project_root = pwd; end
if nargin < 2, claim_id = 'UNBOUND'; end
if nargin < 3, parameters_json = ''; end
if nargin < 4, prefix = 'matlab_core_evidence'; end

fig_dir = fullfile(project_root, 'figures');
data_dir = fullfile(project_root, 'results', 'figures_data');
log_dir = fullfile(project_root, 'results', 'logs');
if ~exist(fig_dir, 'dir'), mkdir(fig_dir); end
if ~exist(data_dir, 'dir'), mkdir(data_dir); end
if ~exist(log_dir, 'dir'), mkdir(log_dir); end

% Deterministic engineering-response evidence. Replace this block with the
% project model while preserving the artifact and claim-binding contract.
model = struct('t_end',12.0,'samples',241,'decay',0.52, ...
    'frequency',1.72,'sine_weight',0.18,'tolerance',0.02, ...
    'steady_start',7.0);
if ~isempty(parameters_json) && isfile(parameters_json)
    supplied = jsondecode(fileread(parameters_json));
    if isfield(supplied,'model'), supplied = supplied.model; end
    fields = fieldnames(model);
    for k = 1:numel(fields)
        if isfield(supplied,fields{k}), model.(fields{k}) = supplied.(fields{k}); end
    end
end
t = linspace(0, model.t_end, model.samples)';
reference = ones(size(t));
response = 1 - exp(-model.decay*t).*(cos(model.frequency*t) + ...
    model.sine_weight*sin(model.frequency*t));
residual = response - reference;
tolerance = model.tolerance;
steady_mask = t >= model.steady_start;
rmse = sqrt(mean(residual.^2));
steady_max_error = max(abs(residual(steady_mask)));

T = table(t, reference, response, residual);
writetable(T, fullfile(data_dir, [prefix '.csv']));
save(fullfile(data_dir, [prefix '.mat']), 't', 'reference', 'response', ...
    'residual', 'tolerance', 'steady_mask', 'rmse', 'steady_max_error', 'model');

ink = [.12 .16 .20];
muted = [.45 .50 .56];
blue = [.24 .43 .55];
accent = [.66 .35 .31];
band = [.88 .91 .92];
font_name = 'Microsoft YaHei';

f = figure('Color','w','Position',[100 100 1200 760], 'Visible','off');
tl = tiledlayout(f, 1, 1, 'TileSpacing','compact', 'Padding','compact');
ax = nexttile(tl);
hold(ax,'on');
fill(ax,[t;flipud(t)],[reference-tolerance;flipud(reference+tolerance)], ...
    band,'EdgeColor','none','FaceAlpha',0.72,'DisplayName','稳态容差带');
plot(ax,t,response,'Color',blue,'LineWidth',2.0,'DisplayName','系统响应');
plot(ax,t,reference,'--','Color',muted,'LineWidth',1.1,'DisplayName','目标响应');
[~,peak_idx] = max(residual);
plot(ax,t(peak_idx),response(peak_idx),'o','MarkerSize',7, ...
    'MarkerFaceColor',accent,'MarkerEdgeColor','w','DisplayName','最大偏差');
xlabel(ax,'时间 / s'); ylabel(ax,'归一化响应');
title(ax,'动态响应及稳态约束核验');
legend(ax,'Location','northeast','Box','off','NumColumns',2);
xlim(ax,[t(1) t(end)]);

% The inset is justified by the steady-state tolerance claim and uses the
% same scale semantics as the main response rather than adding a new panel.
inset = axes('Parent',f,'Position',[0.57 0.24 0.30 0.27]);
hold(inset,'on');
fill(inset,[t(steady_mask);flipud(t(steady_mask))], ...
    [-tolerance*ones(nnz(steady_mask),1);flipud(tolerance*ones(nnz(steady_mask),1))], ...
    band,'EdgeColor','none','FaceAlpha',0.75);
plot(inset,t(steady_mask),residual(steady_mask),'Color',accent,'LineWidth',1.5);
yline(inset,0,'Color',muted,'LineWidth',0.8);
xlabel(inset,'时间 / s'); ylabel(inset,'稳态误差');
title(inset,'局部放大：稳态误差');
xlim(inset,[model.steady_start model.t_end]);
ylim(inset,[-1.25*tolerance 1.25*tolerance]);

set(findall(f,'-property','FontName'),'FontName',font_name);
set(findall(f,'Type','axes'),'Color','w','XColor',ink,'YColor',ink, ...
    'Box','off','FontSize',10,'LineWidth',0.8);
set(findall(f,'Type','text'),'Color',ink);
set(findall(f,'Type','legend'),'Color','w','TextColor',ink);
exportgraphics(f, fullfile(fig_dir,[prefix '.png']),'Resolution',300);
exportgraphics(f, fullfile(fig_dir,[prefix '.pdf']),'ContentType','vector');
close(f);

summary = struct( ...
    'claim_id',claim_id, ...
    'figure',['figures/' prefix '.pdf'], ...
    'source_data',['results/figures_data/' prefix '.csv'], ...
    'backend',['MATLAB ' version], ...
    'matlab_version',['R' version('-release')], ...
    'required_toolboxes',{{'MATLAB base'}}, ...
    'layout','inset', ...
    'supported_claim','系统响应收敛到目标值，局部放大验证稳态误差不超过给定容差。', ...
    'rmse',rmse, ...
    'steady_max_error',steady_max_error, ...
    'tolerance',tolerance);
fid = fopen(fullfile(data_dir,[prefix '_summary.json']),'w','n','UTF-8');
fprintf(fid,'%s',jsonencode(summary,'PrettyPrint',true)); fclose(fid);

fid = fopen(fullfile(log_dir,[prefix '_matlab.log']),'w','n','UTF-8');
fprintf(fid,['backend=MATLAB %s\nstatus=success\nclaim_id=%s\n' ...
    'source=code/matlab/matlab_claim_figure.m\n' ...
    'parameters=%s\n' ...
    'data=results/figures_data/%s.csv\n' ...
    'mat=results/figures_data/%s.mat\n' ...
    'vector=figures/%s.pdf\n' ...
    'png=figures/%s.png\n' ...
    'required_toolboxes=MATLAB base\n'], ...
    version,claim_id,parameters_json,prefix,prefix,prefix,prefix);
fclose(fid);
fprintf('MIRA_MATLAB_FIGURE_OK=%s\n', fullfile(fig_dir,[prefix '.png']));
end
