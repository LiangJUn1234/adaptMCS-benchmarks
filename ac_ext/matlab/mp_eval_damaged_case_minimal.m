function out = mp_eval_damaged_case_minimal(case_data, state_payload, mode, debug, ac_fail_as_violation)
%MP_EVAL_DAMAGED_CASE_MINIMAL Apply damage and evaluate one solver mode fully in MATLAB.
%
% Inputs:
%   case_data               MATPOWER case name or struct
%   state_payload           JSON text or struct
%   mode                    'acpf' | 'acopf' | 'dcpf'
%   debug                   logical
%   ac_fail_as_violation    logical
%
% Output:
%   out struct with:
%       success
%       s_line
%       s_volt
%       s_any

if nargin < 4 || isempty(debug)
    debug = false;
end
if nargin < 5 || isempty(ac_fail_as_violation)
    ac_fail_as_violation = true;
end

mpc_damaged = mp_apply_damage_state_minimal(case_data, state_payload);

mode = lower(char(mode));
switch mode
    case 'acpf'
        out = mp_run_acpf_minimal(mpc_damaged, debug, ac_fail_as_violation);
    case 'acopf'
        out = mp_run_acopf_minimal(mpc_damaged, debug, ac_fail_as_violation);
    case 'dcpf'
        out = mp_run_dcpf_minimal(mpc_damaged, debug, ac_fail_as_violation);
    case 'fdxb'  % <--- 新增的 FDXB 路由分支！
        out = mp_run_fdxb_minimal(mpc_damaged, debug, ac_fail_as_violation);
    otherwise
        error('Unsupported damaged evaluation mode: %s', mode);
end
end
