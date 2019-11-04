from gurobipy import *
from Input.fixed_file_variables import FixedFileVariables
from Input.dynamic_file_variables import DynamicFileVariables
from visualize import draw_routes
from Input.instance_generator import Instance

rand_mode = True

if rand_mode:
    tes = Instance(10, 2, 50)
    f = tes.fixed
    d = tes.dynamic
else:
    f = FixedFileVariables()
    d = DynamicFileVariables()

try:
    m = Model("Bicycle")

    # ------ SETS -----------------------------------------------------------------------------
    Stations = f.stations
    Vehicles = f.vehicles

    # ------ FIXED PARAMETERS -----------------------------------------------------------------
    time_horizon = f.time_horizon
    vehicle_cap = f.vehicle_cap
    station_cap = f.station_cap
    driving_times = f.driving_times
    parking_time = f.parking_time
    handling_time = f.handling_time
    M = f.M
    I_B = f.I_B
    I_V = f.I_V
    w_dev_reward = f.w_dev_reward
    w_driving_times = f.w_driving_time
    w_dev_obj = f.w_dev_obj
    w_reward = f.w_reward
    w_violation = f.w_violation

    # ------- DYNAMIC PARAMETERS --------------------------------------------------------------
    start_stations = d.start_stations
    init_vehicle_load = d.init_vehicle_load
    init_station_load = d.init_station_load
    init_flat_station_load = d.init_flat_station_load
    ideal_state = d.ideal_state
    driving_to_start = d.driving_to_start
    demand = d.demand
    incoming_rate = d.incoming_rate
    incoming_flat_rate = d.incoming_flat_rate

    # ------ VARIABLES -------------------------------------------------------------------------
    x = m.addVars({(i, j, v) for i in Stations
                     for j in Stations for v in Vehicles}, vtype=GRB.BINARY, lb=0, name="x")
    t = m.addVars({i for i in Stations}, vtype=GRB.CONTINUOUS, lb=0, name="t")
    q = m.addVars({(i, v) for i in Stations for v in Vehicles}, vtype=GRB.INTEGER, lb=0, name="q")
    l_B = m.addVars({i for i in Stations}, vtype=GRB.CONTINUOUS, lb=0, name="l_B")
    l_F = m.addVars({i for i in Stations}, vtype=GRB.CONTINUOUS, lb=0, name="l_F")
    l_V = m.addVars({(i, v) for i in Stations for v in Vehicles}, vtype=GRB.INTEGER, lb=0, name="l_V")
    s_B = m.addVars({i for i in Stations}, vtype=GRB.CONTINUOUS, lb=0, name="s_B")
    s_F = m.addVars({i for i in Stations}, vtype=GRB.CONTINUOUS, lb=0, name="s_F")
    s_V = m.addVars({v for v in Vehicles}, vtype=GRB.CONTINUOUS, lb=0, name="s_V")
    v_S = m.addVars({i for i in Stations}, vtype=GRB.CONTINUOUS, lb=0, name="v_S")
    d = m.addVars({i for i in Stations}, vtype=GRB.CONTINUOUS, lb=0, name="d")
    delta = m.addVars({i for i in Stations}, vtype=GRB.BINARY, name="delta")
    gamma = m.addVars({i for i in Stations}, vtype=GRB.BINARY, name="gamma")
    v_Sf = m.addVars({i for i in Stations}, vtype=GRB.CONTINUOUS, name="v_Sf")
    v_SF = m.addVars({i for i in Stations}, vtype=GRB.CONTINUOUS, name="v_SF")
    omega = m.addVars({i for i in Stations}, vtype=GRB.BINARY, name="omega")
    lam = m.addVars({i for i in Stations}, vtype=GRB.BINARY, name="lam")
    r_D = m.addVars({i for i in Stations}, vtype=GRB.CONTINUOUS, lb=0, name="r_D")
    t_f = m.addVars({v for v in Vehicles}, vtype=GRB.CONTINUOUS, lb=0, name="t_f")
    sigma_B = m.addVars({i for i in Stations}, vtype=GRB.BINARY, name="sigma_B")
    sigma_V = m.addVars({v for v in Vehicles}, vtype=GRB.BINARY, name="sigma_V")

    # ------- FEASIBILITY CONSTRAINTS ----------------------------------------------------------
    # Routing constraints
    m.addConstrs(x.sum(start_stations[v], '*', v) == 1 for v in Vehicles)
    m.addConstrs(x.sum('*', Stations[-1], v) == 1 for v in Vehicles)
    for j in Stations[:-1]:
        for v in Vehicles:
            if j != start_stations[v]:
                m.addConstr(x.sum('*', j, v) - x.sum(j, '*', v) == 0)
    m.addConstrs(x.sum('*', j, '*') <= 1 for j in Stations[1:-1])
    m.addConstrs(x.sum('*', 0, v) <= 1 for v in Vehicles)
    m.addConstrs(x.sum('*', '*', v) <= (len(Stations)-1) for v in Vehicles)

    # Time Constraints
    m.addConstrs(t[i] + parking_time + handling_time * q.sum(i, '*') + driving_times[i][j]
                 - t[j] - M * (1-x.sum(i, j, '*')) <= 0 for i in Stations for j in Stations)
    m.addConstrs(t[i] + parking_time + handling_time * q.sum(i, '*') + driving_times[i][j]
                 - t[j] + M * (1 - x.sum(i, j, '*')) >= 0 for i in Stations for j in Stations)
    m.addConstrs(t[start_stations[v]] >= driving_to_start[v] for v in Vehicles)
    m.addConstrs(t[i] - time_horizon - M * x.sum(i, Stations[-1], '*') <= 0 for i in Stations[:-1])
    m.addConstrs(t[i] - M * x.sum(i, '*', '*') <= 0 for i in Stations[:-1])

    # Vehicle Loading Constraints
    m.addConstrs(q[(i, v)] <= l_V[(i, v)] for i in Stations[1:-1] for v in Vehicles)
    m.addConstrs(l_V[(start_stations[v], v)] == init_vehicle_load[v] for v in Vehicles)
    m.addConstrs(
        l_V[(j, v)] - vehicle_cap[v] - M * (1-x[(Stations[0], j, v)]) <= 0 for j in Stations for v in Vehicles)
    m.addConstrs(
        l_V[(j, v)] - vehicle_cap[v] + M * (1 - x[(Stations[0], j, v)]) >= 0 for j in Stations for v in Vehicles)
    m.addConstrs(l_V[(j, v)] - l_V[(i, v)] + q[(i, v)] - M * (
            1 - x[(i, j, v)]) <= 0 for i in Stations[1:] for j in Stations for v in Vehicles)
    m.addConstrs(l_V[(j, v)] - l_V[(i, v)] + q[(i, v)] + M * (
            1 - x[(i, j, v)]) >= 0 for i in Stations[1:] for j in Stations for v in Vehicles)

    # Station Loading Constraints
    m.addConstrs(l_F[i] == init_flat_station_load[i] + incoming_flat_rate[i] * t[i] for i in Stations[1:-1])
    m.addConstrs(l_B[i] == init_station_load[i] + (
            incoming_rate[i] - demand[i]) * t[i] + v_S[i] for i in Stations[1:-1])
    m.addConstrs(q.sum(i, '*') <= l_F[i] for i in Stations[1:-1])
    m.addConstrs(q[(i, v)] - vehicle_cap[v] * x.sum(i, '*', v) <= 0 for i in Stations[1:-1] for v in Vehicles)
    m.addConstrs(l_B[i] - M * (1 - lam[i]) <= 0 for i in Stations[1:])
    m.addConstrs(init_station_load[i] + (incoming_flat_rate[i] - demand[i]) * t[i] + M * lam[i] >= 0 for i in Stations[1:])
    m.addConstrs(q[(0, v)] <= 0 for v in Vehicles)
    m.addConstrs(q[(Stations[-1], v)] <= 0 for v in Vehicles)

    # ------- VIOLATION CONSTRAINTS ------------------------------------------------------------------
    m.addConstrs(t[i] <= time_horizon + M * delta[i] for i in Stations[1:-1])
    m.addConstrs(t[i] >= time_horizon * delta[i] for i in Stations[1:-1])
    m.addConstrs(delta[i] <= x.sum(i, Stations[-1], '*') for i in Stations[:-1])
    m.addConstrs(gamma[i] == x.sum(i, '*', '*') for i in Stations[1:])

    # Situation 1
    m.addConstrs(s_B[i] <= init_station_load[i] + (incoming_flat_rate[i] - demand[i]
                                                    ) * time_horizon + v_Sf[i] + M * gamma[i] for i in Stations[1:-1])
    m.addConstrs(s_B[i] >= init_station_load[i] + (incoming_flat_rate[i] - demand[i]
                                                    ) * time_horizon + v_Sf[i] - M * gamma[i] for i in Stations[1:-1])
    m.addConstrs(s_F[i] <= init_flat_station_load[i] +
                 incoming_flat_rate[i] * time_horizon + M * gamma[i] for i in Stations[1:-1])
    m.addConstrs(s_F[i] >= init_flat_station_load[i] +
                 incoming_flat_rate[i] * time_horizon - M * gamma[i] for i in Stations[1:-1])

    # Situation 2
    m.addConstrs(s_B[i] <= l_B[i] + q.sum(i, '*') + (incoming_rate[i]-demand[i]) * (
                time_horizon - t[i]) + v_Sf[i] + M * delta[i] for i in Stations[1:-1])
    m.addConstrs(s_B[i] >= l_B[i] + q.sum(i, '*') + (incoming_rate[i] - demand[i]) * (
                time_horizon - t[i]) + v_Sf[i] - M * delta[i] for i in Stations[1:-1])
    m.addConstrs(s_F[i] <= l_F[i] - q.sum(i, '*') + incoming_flat_rate[i] * (
                time_horizon - t[i]) + M * delta[i] for i in Stations[1:-1])
    m.addConstrs(s_F[i] >= l_F[i] - q.sum(i, '*') + incoming_flat_rate[i] * (
                time_horizon - t[i]) - M * delta[i] for i in Stations[1:-1])

    # Situation 3
    m.addConstrs(-s_B[i] <= -l_B[i] + (incoming_rate[i] - demand[i]) * (
                t[i] - time_horizon) + v_SF[i] + M * (1 - delta[i]) for i in Stations[1:-1])
    m.addConstrs(-s_B[i] >= -l_B[i] + (incoming_rate[i] - demand[i]) * (
            t[i] - time_horizon) + v_SF[i] - M * (1 - delta[i]) for i in Stations[1:-1])
    m.addConstrs(-s_F[i] <= -l_F[i] + incoming_flat_rate[i] * (t[i]-time_horizon) + M * (1 - delta[i]
                                                                                       ) for i in Stations[1:-1])
    m.addConstrs(-s_F[i] >= -l_F[i] + incoming_flat_rate[i] * (t[i] - time_horizon) - M * (1 - delta[i]
                                                                                         ) for i in Stations[1:-1])
    m.addConstrs(l_B[i] + station_cap[i] * omega[i] <= station_cap[i] for i in Stations[1:-1])
    m.addConstrs(1 - omega[i] <= l_B[i] for i in Stations[1:-1])
    m.addConstrs((v_S[i]-v_SF[i]) - M * (omega[i] - delta[i] + 1) <= 0 for i in Stations[1:-1])
    m.addConstr(delta[0] <= 0)
    m.addConstrs(v_SF[i] <= M * delta[i] for i in Stations[1:-1])
    m.addConstrs(v_SF[i] - M * (1 - delta[i]) <= v_S[i] for i in Stations[1:-1])

    # ------- DEVIATIONS -----------------------------------------------------------------------------
    m.addConstrs(d[i] >= ideal_state[i] - s_B[i] for i in Stations[1:-1])
    m.addConstrs(d[i] >= s_B[i] - ideal_state[i] for i in Stations[1:-1])
    
    # ------- OBJECTIVE CONSTRAINTS ------------------------------------------------------------------
    m.addConstrs(s_V[v] <= l_V[(i, v)] + (2 - delta[j] + delta[i] - x[(i, j, v)]) * vehicle_cap[v]
                 for i in Stations[1:-1] for j in Stations[1:-1] for v in Vehicles)
    m.addConstrs(s_V[v] >= l_V[(i, v)] - (2 - delta[j] + delta[i] - x[(i, j, v)]) * vehicle_cap[v]
                 for i in Stations[1:-1] for j in Stations[1:-1] for v in Vehicles)
    
    m.addConstrs(s_V[v] >= l_V[(i, v)] - q[(i, v)]-(
            1-x[(i, Stations[-1], v)]) * M for i in Stations for v in Vehicles)
    m.addConstrs(s_V[v] <= l_V[(i, v)] - q[(i, v)] + (
            1 - x[(i, Stations[-1], v)]) * M for i in Stations for v in Vehicles)
    m.addConstrs(r_D[i] <= d[i] + station_cap[i] * (1 - delta[i])
                 for i in Stations[1:-1] for j in Stations[1:-1] for v in Vehicles)
    m.addConstrs(r_D[i] <= delta[i] * station_cap[i] for i in Stations[1:-1])
    m.addConstrs(s_V[v] <= I_V + vehicle_cap[v] * sigma_V[v] for v in Vehicles)
    m.addConstrs(s_B[i] <= I_B + station_cap[i] * sigma_B[i] for i in Stations[1:-1])
    m.addConstrs(x[(i, Stations[-1], v)] <= 2 - sigma_V[v] - delta[i] for i in Stations for v in Vehicles)
    m.addConstrs(x[(i, Stations[-1], v)] <= 2 - sigma_B[v] - delta[i] for i in Stations for v in Vehicles)
    m.addConstr(r_D[Stations[-1]] <= 0)
    m.addConstr(r_D[Stations[0]] <= 0)
    m.addConstrs(t_f[v] - t[i] + time_horizon - M * (1 - x[(i, Stations[-1], v)]) <= 0
                 for i in Stations for v in Vehicles)
    m.addConstrs(t_f[v] - t[i] + time_horizon + M * (1 - x[(i, Stations[-1], v)]) >= 0
                 for i in Stations for v in Vehicles)

    # ------- OBJECTIVE ------------------------------------------------------------------------------
    m.setObjective(w_violation * (v_S.sum('*')+v_SF.sum('*')+v_Sf.sum('*')) + w_dev_obj * d.sum('*')
                   - w_reward * (w_dev_reward * r_D.sum('*') - w_driving_times * t_f.sum('*')), GRB.MINIMIZE)
    # m.setObjective(v_S.sum('*')+v_SF.sum('*')+v_Sf.sum('*') + d.sum('*'), GRB.MINIMIZE)

    m.optimize()

    # ------- VISUALIZE ------------------------------------------------------------------------------
    route_dict = {}
    for v in m.getVars():
        if v.varName[0] == 'x' and v.x == 1:
            t = float(m.getVarByName("t[{}]".format(v.varName[2])).x)
            dist = driving_times[int(v.varName[2])][int(v.varName[4])]
            arch = [int(v.varName[2]), int(v.varName[4]), t, dist]
            if int(v.varName[-2]) not in route_dict.keys():
                route_dict[int(v.varName[-2])] = [arch]
            else:
                route = route_dict[int(v.varName[-2])]
                for i in range(len(route)):
                    if route[i][-2] > t:
                        route.insert(i, arch)
                        break
                    else:
                        if i == len(route_dict[int(v.varName[-2])])-1:
                            route.append(arch)
        print(v.varName, v.x)
    draw_routes(route_dict, Stations)
    print(route_dict)
    print("Obj: ", m.objVal)

except GurobiError:
    print("Error")
