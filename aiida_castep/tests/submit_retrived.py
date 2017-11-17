


StructureData = DataFactory("structure")
ParameterData = DataFactory("parameter")
KpointsData = DataFactory("array.kpoints")
OTFGData = DataFactory("castep.otfgdata")
CastepCalculation = CalculationFactory("castep.castep")

code = Code.get_from_string("castep-17.2@localhost")
calc = code.new_calc()

cell = ((3, 0, 0),
    (0, 3, 0),
    (0,0,3))
structure = StructureData(cell=cell)
structure.append_atom(symbols="H", position=(0,0,0))
structure.append_atom(symbols="H", position=(1,0,0))

input_dict = {"CELL":
                {},
                "PARAM":{
                "xc_functional" : "lda",
                "iprint": "1",
                "cut_off_energy" : 200,
                "task" :"geometryoptimisation"
                }}

input_param = ParameterData(dict=input_dict)
kpoints = KpointsData(kpoints_mesh=(4,4,4))
code = Code.get_from_string("castep-17.2@localhost")
C9 = OTFGData.get_or_create("C9")[0]

calc.set_resources({"num_machines":1})


calc.use_pseudo(C9, kind="H")
calc.use_parameters(input_param)
calc.use_kpoints(kpoints)
calc.use_structure(structure)
calc.store_all()
print(calc.pk)
calc.submit()
print("DONE")
