"""Read Vectorworks Braceworks cross-section XML into normalized SI data."""

import os
import sys
import xml.etree.ElementTree as ET

from rigcalc.model import MechanicalSection


CM2_TO_M2 = 1.0e-4
CM4_TO_M4 = 1.0e-8
KN_TO_N = 1000.0
KNM_TO_NM = 1000.0


def _number(node, name):
    child = node.find(name)
    if child is None or child.text is None:
        return None
    try:
        return float(child.text.strip().replace(",", "."))
    except ValueError:
        return None


def _text(node, name):
    child = node.find(name)
    return child.text.strip() if child is not None and child.text else ""


def _xml_files(directory):
    if not directory or not os.path.isdir(directory):
        return []
    return [os.path.join(directory, name) for name in os.listdir(directory)
            if name.lower().endswith(".xml")]


def _parse_material(path):
    root = ET.parse(path).getroot()
    file_id = os.path.splitext(os.path.basename(path))[0]
    xml_id = root.get("Ident", "")
    material_name = _text(root, "MaterialName") or xml_id or file_id
    issues = []
    if xml_id and xml_id != file_id:
        issues.append("material_file_identifier_mismatch:{}:{}".format(
            file_id, xml_id))
    if material_name and material_name not in (file_id, xml_id):
        issues.append("material_name_identifier_mismatch:{}:{}".format(
            file_id, material_name))
    return {
        "keys": {value for value in (file_id, xml_id, material_name) if value},
        "name": material_name,
        "elastic_modulus_pa": _number(root, "EModul_Pascal"),
        "shear_modulus_pa": _number(root, "GModul_Pascal"),
        "poisson_ratio": _number(root, "V_None"),
        "density_kg_m3": _number(root, "Density_KGM3"),
        "source_path": path,
        "issues": issues,
    }


def _material_lookup(material_directories):
    result = {}
    for directory in material_directories:
        for path in _xml_files(directory):
            try:
                material = _parse_material(path)
            except (ET.ParseError, OSError):
                continue
            for key in material["keys"]:
                result[key] = material
    return result


def load_section_library(roots):
    """Load section databases; later roots override earlier roots."""
    roots = [path for path in roots if path and os.path.isdir(path)]
    materials = _material_lookup(
        [os.path.join(root, "Materials") for root in roots])
    sections = {}
    for root in roots:
        for path in _xml_files(os.path.join(root, "Sections")):
            try:
                xml = ET.parse(path).getroot()
            except (ET.ParseError, OSError):
                continue
            file_id = os.path.splitext(os.path.basename(path))[0]
            identifier = xml.get("Ident", "") or file_id
            name = _text(xml, "SectionName") or identifier
            material_id = xml.get("MaterialName", "")
            material = materials.get(material_id)
            issues = []
            if identifier != file_id:
                issues.append("section_file_identifier_mismatch:{}:{}".format(
                    file_id, identifier))
            if material is None:
                issues.append("material_not_found:{}".format(material_id))
                material = {}
            issues.extend(material.get("issues", []))
            section = MechanicalSection(
                identifier=identifier, name=name,
                manufacturer=_text(xml, "SectionManufactor"),
                material_name=material_id,
                area_m2=_scaled(xml, "CrossAreaSection_CM2", CM2_TO_M2),
                shear_area_y_m2=_scaled(xml, "Ay_CM2", CM2_TO_M2),
                shear_area_z_m2=_scaled(xml, "Az_CM2", CM2_TO_M2),
                ixx_m4=_scaled(xml, "Ixx_CM4", CM4_TO_M4),
                iyy_m4=_scaled(xml, "Iyy_CM4", CM4_TO_M4),
                izz_m4=_scaled(xml, "Izz_CM4", CM4_TO_M4),
                elastic_modulus_pa=material.get("elastic_modulus_pa"),
                shear_modulus_pa=material.get("shear_modulus_pa"),
                poisson_ratio=material.get("poisson_ratio"),
                density_kg_m3=material.get("density_kg_m3"),
                source_path=path,
                max_axial_n=_positive_scaled(xml, "MaxNx_KN", KN_TO_N),
                max_shear_y_n=_positive_scaled(xml, "MaxVy_KN", KN_TO_N),
                max_shear_z_n=_positive_scaled(xml, "MaxVz_KN", KN_TO_N),
                max_torsion_nm=_positive_scaled(
                    xml, "MaxMt_KNM", KNM_TO_NM),
                max_moment_y_nm=_positive_scaled(
                    xml, "MaxMby_KNM", KNM_TO_NM),
                max_moment_z_nm=_positive_scaled(
                    xml, "MaxMbz_KNM", KNM_TO_NM),
                material_source_path=material.get("source_path", ""),
                issues=issues,
            )
            for key in {file_id, identifier, name}:
                if key:
                    sections[key] = section
    return sections


def _scaled(node, name, factor):
    value = _number(node, name)
    return None if value is None else value * factor


def _positive_scaled(node, name, factor):
    value = _scaled(node, name, factor)
    return value if value is not None and value > 0.0 else None


def default_cross_section_roots():
    """Return installed then user roots, allowing user data to override."""
    candidates = []
    install_root = os.path.dirname(os.path.dirname(sys.executable))
    candidates.append(os.path.join(
        install_root, "Plug-Ins", "VW_Spotlight", "Data", "Braceworks",
        "TrussCrossSectionData"))
    program_files = os.environ.get("ProgramFiles")
    if program_files:
        candidates.append(os.path.join(
            program_files, "Vectorworks 2026", "Plug-Ins", "VW_Spotlight",
            "Data", "Braceworks", "TrussCrossSectionData"))
    appdata = os.environ.get("APPDATA")
    if appdata:
        user_base = os.path.join(
            appdata, "Nemetschek", "Vectorworks", "2026")
        candidates.extend([
            os.path.join(user_base, "Plug-Ins", "VW_Spotlight", "Data",
                         "Braceworks", "TrussCrossSectionData"),
            os.path.join(user_base, "Libraries", "Defaults", "Braceworks",
                         "TrussCrossSectionData"),
        ])
    unique = []
    for path in candidates:
        normalized = os.path.normcase(os.path.normpath(path))
        if normalized not in {os.path.normcase(os.path.normpath(p)) for p in unique}:
            unique.append(path)
    return unique


def assign_cross_sections(trusses, roots=None):
    library = load_section_library(
        default_cross_section_roots() if roots is None else roots)
    for truss in trusses:
        identifier = truss.cross_section_id.strip()
        if not identifier:
            truss.cross_section_issues.append("cross_section_id_missing")
            continue
        section = library.get(identifier)
        if section is None:
            truss.cross_section_issues.append(
                "cross_section_not_found:{}".format(identifier))
            continue
        truss.mechanical_section = section
        truss.cross_section_issues.extend(section.issues)
    return library
