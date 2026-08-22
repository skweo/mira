function matlab_geometry_3d(project_root, claim_id, parameters_json, prefix)
% Reproducible claim-bearing 3D face-vertex geometry with a 2D companion view.
if nargin < 1, project_root = pwd; end
if nargin < 2, claim_id = 'UNBOUND'; end
if nargin < 3, parameters_json = ''; end
if nargin < 4, prefix = 'matlab_geometry_3d'; end

fig_dir = fullfile(project_root, 'figures');
data_dir = fullfile(project_root, 'results', 'figures_data');
log_dir = fullfile(project_root, 'results', 'logs');
if ~exist(fig_dir, 'dir'), mkdir(fig_dir); end
if ~exist(data_dir, 'dir'), mkdir(data_dir); end
if ~exist(log_dir, 'dir'), mkdir(log_dir); end

payload = default_payload();
if ~isempty(parameters_json) && isfile(parameters_json)
    supplied = jsondecode(fileread(parameters_json));
    if isfield(supplied, 'geometry')
        payload.geometry = merge_struct(payload.geometry, supplied.geometry);
    end
    if isfield(supplied, 'display')
        payload.display = merge_struct(payload.display, supplied.display);
    end
end

geometry = payload.geometry;
display = payload.display;
vertices = double(geometry.vertices);
faces = double(geometry.faces);
face_values = double(geometry.face_values(:));
validateattributes(vertices, {'numeric'}, {'2d','ncols',3,'finite','real'});
validateattributes(faces, {'numeric'}, {'2d','real'});
face_indices = faces(~isnan(faces));
if isempty(face_indices) || any(face_indices < 1) || any(face_indices > size(vertices,1)) || any(mod(face_indices,1) ~= 0)
    error('Mira:InvalidFaces', 'Faces must contain valid one-based vertex indices.');
end

if numel(face_values) == size(faces,1)
    face_color = 'flat';
    color_mapping = 'face';
elseif numel(face_values) == size(vertices,1)
    face_color = 'interp';
    color_mapping = 'vertex';
else
    error('Mira:InvalidColorData', 'face_values must contain one value per face or per vertex.');
end
display.color_mapping = color_mapping;

view_angles = row_vector(display.view, 2, 'display.view');
aspect = row_vector(display.data_aspect_ratio, 3, 'display.data_aspect_ratio');
light_position = row_vector(display.light_position, 3, 'display.light_position');
validateattributes(display.face_alpha, {'numeric'}, {'scalar','>',0,'<=',1});
projection_plane = lower(char(display.projection_plane));
if ~ismember(projection_plane, {'xy','xz','yz'})
    error('Mira:InvalidProjection', 'projection_plane must be xy, xz, or yz.');
end
display.view = view_angles;
display.data_aspect_ratio = aspect;
display.light_position = light_position;
display.projection_plane = projection_plane;

ink = [0.15 0.20 0.22];
grid_color = [0.82 0.85 0.84];
edge_color = [0.24 0.31 0.33];
if strcmpi(char(display.edge_mode), 'none')
    edge_color = 'none';
end

% Freeze the audited geometry inputs before rendering so every exported
% figure is newer than the data it represents.
vertex_id = (1:size(vertices,1))';
vertex_table = table(vertex_id, vertices(:,1), vertices(:,2), vertices(:,3), ...
    'VariableNames', {'vertex_id','x','y','z'});
writetable(vertex_table, fullfile(data_dir,[prefix '.csv']));
save(fullfile(data_dir,[prefix '.mat']), 'vertices','faces','face_values','display','claim_id');

f = figure('Color','w','Position',[100 100 980 720],'Visible','off');
ax = axes(f);
p = patch(ax, 'Faces',faces, 'Vertices',vertices, ...
    'FaceVertexCData',face_values, 'FaceColor',face_color, ...
    'CDataMapping','scaled', 'FaceAlpha',display.face_alpha, ...
    'EdgeColor',edge_color, 'LineWidth',0.65);
colormap(ax, geometry_colormap(char(display.colormap)));
if max(face_values) > min(face_values)
    clim(ax, [min(face_values) max(face_values)]);
end
cb = colorbar(ax);
cb.Label.String = 'geometry value';
cb.Color = ink;
view(ax, view_angles(1), view_angles(2));
daspect(ax, aspect);
axis(ax, 'vis3d');
axis(ax, 'tight');
grid(ax, 'on');
box(ax, 'on');
xlabel(ax, axis_label('x', geometry.unit));
ylabel(ax, axis_label('y', geometry.unit));
zlabel(ax, axis_label('z', geometry.unit));
set(ax, 'FontName','Arial', 'FontSize',10.5, 'LineWidth',0.8, ...
    'Color','w', 'XColor',ink, 'YColor',ink, 'ZColor',ink, ...
    'GridColor',grid_color, 'GridAlpha',0.35);
p.FaceLighting = char(display.lighting);
if ~strcmpi(char(display.lighting), 'none')
    light(ax, 'Position',light_position, 'Style','infinite', 'Color',[1 1 1]);
    material(ax, char(display.material));
end
exportgraphics(f, fullfile(fig_dir,[prefix '.png']), 'Resolution',300);
exportgraphics(f, fullfile(fig_dir,[prefix '.pdf']), 'ContentType','vector');
close(f);

projection_png = fullfile(fig_dir,[prefix '_projection.png']);
projection_pdf = fullfile(fig_dir,[prefix '_projection.pdf']);
fp = figure('Color','w','Position',[100 100 760 650],'Visible','off');
ap = axes(fp);
patch(ap, 'Faces',faces, 'Vertices',vertices, 'FaceColor',[0.55 0.68 0.69], ...
    'FaceAlpha',0.22, 'EdgeColor',edge_color, 'LineWidth',0.9);
set_projection(ap, projection_plane);
daspect(ap, aspect);
axis(ap, 'tight');
grid(ap, 'on');
box(ap, 'on');
set(ap, 'FontName','Arial', 'FontSize',10.5, 'LineWidth',0.8, ...
    'Color','w', 'XColor',ink, 'YColor',ink, 'ZColor',ink, ...
    'GridColor',grid_color, 'GridAlpha',0.35);
label_projection(ap, projection_plane, geometry.unit);
exportgraphics(fp, projection_png, 'Resolution',300);
exportgraphics(fp, projection_pdf, 'ContentType','vector');
close(fp);

extents = max(vertices,[],1) - min(vertices,[],1);
summary = struct( ...
    'claim_id',claim_id, ...
    'figure',['figures/' prefix '.pdf'], ...
    'projection',['figures/' prefix '_projection.pdf'], ...
    'source_data',['results/figures_data/' prefix '.csv'], ...
    'backend',['MATLAB ' version], ...
    'matlab_version',['R' version('-release')], ...
    'required_toolboxes',{{'MATLAB base'}}, ...
    'supported_claim','The archived face-vertex mesh reproduces the stated spatial structure.', ...
    'prohibited_claim','Rendering completeness does not prove physical feasibility.', ...
    'vertex_count',size(vertices,1), ...
    'face_count',size(faces,1), ...
    'x_extent',extents(1), ...
    'y_extent',extents(2), ...
    'z_extent',extents(3), ...
    'display_parameters',display);
fid = fopen(fullfile(data_dir,[prefix '_summary.json']), 'w', 'n', 'UTF-8');
fprintf(fid, '%s', jsonencode(summary,'PrettyPrint',true));
fclose(fid);

fid = fopen(fullfile(log_dir,[prefix '_matlab.log']), 'w', 'n', 'UTF-8');
fprintf(fid, ['backend=MATLAB %s\nstatus=success\nclaim_id=%s\n' ...
    'source=code/matlab/matlab_geometry_3d.m\nparameters=%s\n' ...
    'vertices=%d\nfaces=%d\nview=%s\naspect=%s\nface_alpha=%.6g\n' ...
    'color_mapping=%s\ncolormap=%s\nlighting=%s\nlight_position=%s\nmaterial=%s\n' ...
    'projection_plane=%s\nrequired_toolboxes=MATLAB base\n'], ...
    version, claim_id, parameters_json, size(vertices,1), size(faces,1), ...
    mat2str(view_angles), mat2str(aspect), display.face_alpha, ...
    char(display.color_mapping), char(display.colormap), char(display.lighting), ...
    mat2str(light_position), char(display.material), projection_plane);
fclose(fid);
fprintf('MIRA_MATLAB_FIGURE_OK=%s\n', fullfile(fig_dir,[prefix '.png']));
end

function payload = default_payload()
payload.geometry = struct( ...
    'vertices',[-1 -0.8 0; 1 -0.8 0; 0.8 0.8 0; -0.8 0.8 0; ...
        -0.6 -0.5 1.4; 0.6 -0.5 1.4; 0.5 0.5 1.4; -0.5 0.5 1.4], ...
    'faces',[1 2 3 4; 5 8 7 6; 1 5 6 2; 2 6 7 3; 3 7 8 4; 4 8 5 1], ...
    'face_values',[0.15; 0.35; 0.55; 0.75; 0.95; 0.60], ...
    'unit','m');
payload.display = struct( ...
    'view',[-35 24], ...
    'data_aspect_ratio',[1 1 1], ...
    'face_alpha',0.92, ...
    'color_mapping','face', ...
    'colormap','mira_muted', ...
    'lighting','gouraud', ...
    'light_position',[-0.6 0.4 1.0], ...
    'material','dull', ...
    'edge_mode','subtle', ...
    'projection_plane','xy');
end

function base = merge_struct(base, supplied)
fields = fieldnames(supplied);
for k = 1:numel(fields)
    base.(fields{k}) = supplied.(fields{k});
end
end

function value = row_vector(value, count, label)
value = double(value(:)');
if numel(value) ~= count || any(~isfinite(value))
    error('Mira:InvalidDisplay', '%s must contain %d finite values.', label, count);
end
end

function map = geometry_colormap(name)
switch lower(name)
    case 'gray'
        map = gray(64);
    case 'copper'
        map = copper(64);
    case 'parula'
        map = parula(64);
    otherwise
        anchors = [0.15 0.20 0.22; 0.30 0.47 0.50; 0.68 0.75 0.72; 0.68 0.56 0.37];
        map = interp1(linspace(0,1,size(anchors,1)), anchors, linspace(0,1,64), 'pchip');
        map = min(max(map,0),1);
end
end

function label = axis_label(symbol, unit)
unit = char(unit);
if isempty(strtrim(unit))
    label = symbol;
else
    label = sprintf('%s / %s', symbol, unit);
end
end

function set_projection(ax, plane)
switch plane
    case 'xy'
        view(ax, 0, 90);
    case 'xz'
        view(ax, 0, 0);
    case 'yz'
        view(ax, 90, 0);
end
end

function label_projection(ax, plane, unit)
switch plane
    case 'xy'
        xlabel(ax, axis_label('x',unit)); ylabel(ax, axis_label('y',unit));
    case 'xz'
        xlabel(ax, axis_label('x',unit)); zlabel(ax, axis_label('z',unit));
    case 'yz'
        ylabel(ax, axis_label('y',unit)); zlabel(ax, axis_label('z',unit));
end
end
