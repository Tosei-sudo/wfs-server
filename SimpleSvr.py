# coding: utf-8
import BaseHTTPServer
import SimpleHTTPServer
from urlparse import urlparse, parse_qs

import json
import uuid

import xml.etree.ElementTree as ET

layers = {
    "mesh" : {
        "data": "mesh.geojson",
        "name"  : "mesh",
        "description" : "mesh",
        "id_field" : "id",
    },
    "stations" : {
        "data": "stations.geojson",
        "name"  : "stations",
        "description" : "stations",
        "id_field" : "id",
    },
}


namespaces = {
    "xmlns:xsi" : "http://www.w3.org/2001/XMLSchema-instance",
    "xmlns" : "http://www.opengis.net/wfs",
    "xmlns:wfs" : "http://www.opengis.net/wfs",
    "xmlns:ogc" : "http://www.opengis.net/ogc",
    "xmlns:gml" : "http://www.opengis.net/gml",
    "xmlns:ows" : "http://www.opengis.net/ows",
    "xmlns:xlink" : "http://www.w3.org/1999/xlink",
    "xmlns:xs" : "http://www.w3.org/2001/XMLSchema",
    "xsi:schemaLocation" : "http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-capabilities.xsd",
}

def get_CapabilitiesXML():
    with open("template/GetCapabilities.xml", "r") as f:
        root = ET.fromstring(f.read())
    
    FeatureTypeList = ET.SubElement(root, "FeatureTypeList")
    for key in layers.keys():
        layer = layers[key]
        FeatureType = ET.SubElement(FeatureTypeList, "FeatureType")
        ET.SubElement(FeatureType, "Name").text = layer["name"]
        ET.SubElement(FeatureType, "Title").text = layer["description"]
        ET.SubElement(FeatureType, "SRS").text = "EPSG:4326"
        
        with open(layer["data"], "r") as f:
            geojson = json.load(f)
        
        lats = [feature["geometry"]["coordinates"][1] for feature in geojson["features"]]
        lons = [feature["geometry"]["coordinates"][0] for feature in geojson["features"]]
        
        ET.SubElement(FeatureType, "LatLongBoundingBox", {
            "minx" : str(min(lons)),
            "miny" : str(min(lats)),
            "maxx" : str(max(lons)),
            "maxy" : str(max(lats))
        })
        
        Operations = ET.SubElement(FeatureType, "Operations")
        ET.SubElement(Operations, "Query")
        ET.SubElement(Operations, "Insert")
        ET.SubElement(Operations, "Update")
        ET.SubElement(Operations, "Delete")
        
    return '<?xml version="1.0" encoding="UTF-8"?>' + ET.tostring(root)

def get_DescribeFeatureTypeXML(type_name):
    attr = {
        "version" : "1.0",
        "elementFormDefault" : "qualified",
        "targetNamespace" : "http://www.qgis.org/gml",
        "xmlns:ogc" : "http://www.opengis.net/ogc",
        "xmlns:xsd" : "http://www.w3.org/2001/XMLSchema",
        "xmlns" : "http://www.w3.org/2001/XMLSchema",
        "xmlns:qgs" : "http://www.qgis.org/gml",
        "xmlns:gml" : "http://www.opengis.net/gml",
    }
    root = ET.Element("schema", attr)
    
    ET.SubElement(root, "import", {"schemaLocation": "http://schemas.opengis.net/gml/3.1.1/base/gml.xsd", "namespace": "http://www.opengis.net/gml"})
    ET.SubElement(root, "element", {"type": "qgs:" + type_name, "substitutionGroup" : "gml:_Feature", "name": type_name})
    
    complexType = ET.SubElement(root, "complexType", {"name": type_name})
    complexContent = ET.SubElement(complexType, "complexContent")
    extension = ET.SubElement(complexContent, "extension", {"base": "gml:AbstractFeatureType"})
    sequence = ET.SubElement(extension, "sequence")
    
    ET.SubElement(sequence, "element", {"name": "geometry", "type": "gml:PointPropertyType", "minOccurs" : "0"})
    
    with open("{0}.geojson".format(type_name), "r") as f:
        geojson = json.load(f)
    
    for key in geojson["features"][0]["properties"].keys():
        value = geojson["features"][0]["properties"][key]
        
        if type(value) is float:
            ET.SubElement(sequence, "element", {"name": key, "type": "double"})
        elif type(value) is int:
            ET.SubElement(sequence, "element", {"name": key, "type": "int"})
        elif key == layers[type_name]["id_field"]:
            ET.SubElement(sequence, "element", {"name": key, "type": "string"})
        else:
            ET.SubElement(sequence, "element", {"name": key, "type": "string"})
    
    return ET.tostring(root)

def geojson_to_GetFeatureXML(type_name):
    with open("{0}.geojson".format(type_name), "r") as f:
        geojson = json.load(f)
        
    root = ET.Element("wfs:FeatureCollection", {
        "xmlns:wfs" : "http://www.opengis.net/wfs",
        "xmlns:ogc" : "http://www.opengis.net/ogc",
        "xmlns:gml" : "http://www.opengis.net/gml",
        "xmlns:ows" : "http://www.opengis.net/ows",
        "xmlns:xlink" : "http://www.w3.org/1999/xlink",
        "xmlns:qgs" : "http://www.qgis.org/gml",
        "xmlns:xsi" : "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:schemaLocation" : "http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.1.0/wfs.xsd http://www.qgis.org/gml",
    })
    
    id_field = layers[type_name]["id_field"]
    
    index = 0
    
    for feature in geojson["features"]:
        properties = feature["properties"]
        
        featureElement = ET.SubElement(root, "gml:featureMember")
        record = ET.SubElement(featureElement, "qgs:" + type_name, {"gml:id": "{0}.{1}".format(type_name, properties[id_field])})
        geometry = ET.SubElement(record, "qgs:geometry")
        Point = ET.SubElement(geometry, "gml:Point" , {"srsName": "EPSG:4326"})
        coordinates = ET.SubElement(Point, "gml:coordinates")
        coordinates.text = "{0},{1}".format(feature["geometry"]["coordinates"][0], feature["geometry"]["coordinates"][1])
        
        for key in properties.keys():
            if (type(properties[key]) is float) or (type(properties[key]) is int):
                properties[key] = str(properties[key])
            ET.SubElement(record, "qgs:" + key).text = properties[key].encode('unicode-escape')
        
        index += 1

    return "<?xml version=\"1.0\" ?>" + ET.tostring(root)

class MainServerHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    
    def send_response(self, code = 200, data=None, extend={}):
        SimpleHTTPServer.SimpleHTTPRequestHandler.send_response(self, code)
        
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        
        if data:
            self.send_header('Content-Length', str(len(data)))        
        self.send_header('Connection', 'close')
        
        for key in extend.keys():
            self.send_header(key, extend[key])
        
        self.end_headers()
        
        self.wfile.write(data)
    
    def do_GET(self):
        
        response_string = ""

        query = urlparse(self.path).query
        query_components = parse_qs(query)
        
        service = query_components["SERVICE"][0]
        request = query_components["REQUEST"][0]
        
        if(self.path.startswith('/wfs')):
            if service == "WFS":
                if request == "GetCapabilities":
                    response_string = get_CapabilitiesXML()
                    
                elif request == "DescribeFeatureType":
                    type_name = query_components["TYPENAME"][0]
                    
                    response_string = get_DescribeFeatureTypeXML(type_name)
                    # self.wfile.write(open("DescribeFeatureType/{0}.xml".format(type_name)).read())
                    
                elif request == "GetFeature":
                    type_name = query_components["TYPENAME"][0]
                    
                    response_string = geojson_to_GetFeatureXML(type_name)
                else:
                    response_string  = open("Error.xml").read()
                    
        self.send_response(200, response_string, extend = {
            "Content-Type": "text/xml"
        })
        
    def do_POST(self):
        
        query = urlparse(self.path).query
        query_components = parse_qs(query)
        
        body_length = int(self.headers['Content-Length'])
        body = self.rfile.read(body_length)
        tree = ET.fromstring(body)
        
        operation = tree.tag.split("}")[-1]
        
        response_string = ""
    
        if(self.path.startswith('/wfs')):
            if operation == "GetCapabilities":
                response_string = get_CapabilitiesXML()
                
            elif operation == "DescribeFeatureType":
        
                type_name = tree[0].attrib["typeName"].split(":")[-1]
                
                response_string = get_DescribeFeatureTypeXML(type_name)
                # self.wfile.write(open("DescribeFeatureType/{0}.xml".format(type_name)).read())
                
            elif operation == "GetFeature":
        
                type_name = tree[0].attrib["typeName"].split(":")[-1]
                    
                response_string = geojson_to_GetFeatureXML(type_name)
            elif operation == "Transaction":
                result_xml = ET.Element("wfs:TransactionResponse", namespaces)
                
                with open("req.xml", "w") as f:
                    f.write(body)
                
                transaction_xml = ET.fromstring(body)
                
                total_inserted = 0
                total_updated = 0
                total_deleted = 0
                
                insert_results = []
                
                for record in transaction_xml:
                    operation = record.tag.split("}")[-1]

                    if operation == "Insert":
                        try:
                            type_name = record[0].tag.split("}")[-1]

                            with open("{0}.geojson".format(type_name), "r") as f:
                                geojson = json.load(f)
                            coordinates = []
                            
                            uid = str(uuid.uuid4())
                            
                            properties = {
                                "id" : uid
                            }
                            for key in record[0]:
                                if key.tag.split("}")[-1] == "geometry":
                                    for point in key[0]:
                                        coordinates.append(map(float, point.text.split(" ")))
                                    continue
                                properties[key.tag.split("}")[-1]] = key.text
                            
                            if len(coordinates) == 1:
                                coordinates = coordinates[0]
                                
                            feature = {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Point",
                                    "coordinates": coordinates
                                },
                                "properties": properties
                            }
                            geojson["features"].append(feature)
                            
                            with open("{0}.geojson".format(type_name), "w") as f:
                                json.dump(geojson, f)
                            
                            featureMember = ET.Element("wfs:Feature", {"handle" : "RoadBalance.{0}".format(uid)})
                            ET.SubElement(featureMember, "ogc:FeatureId", {"fid": "{0}.{1}".format(type_name, uid)})
                            
                            insert_results.append(featureMember)
                            
                            total_inserted += 1
                        except Exception as e:
                            print(e)
                            pass
                    elif operation == "Delete":
                        try:
                            type_name = record.attrib["typeName"]
                            
                            id_field = layers[type_name]["id_field"]
                            
                            with open("{0}.geojson".format(type_name), "r") as f:
                                geojson = json.load(f)
                            for feature_record in record[0]:
                                feature_id = feature_record.attrib["fid"].split(".")[-1]
                                
                                for feature in geojson["features"]:
                                    if feature["properties"][id_field] == feature_id:
                                        geojson["features"].remove(feature)
                                        break
                                
                            with open("{0}.geojson".format(type_name), "w") as f:
                                json.dump(geojson, f)
                                
                            total_deleted += 1
                        except Exception as e:
                            print(e)
                            pass

                TransactionSummary = ET.SubElement(result_xml, "wfs:TransactionSummary")
                
                ET.SubElement(TransactionSummary, "wfs:totalInserted").text = str(total_inserted)
                ET.SubElement(TransactionSummary, "wfs:totalUpdated").text = str(total_updated)
                ET.SubElement(TransactionSummary, "wfs:totalDeleted").text = str(total_deleted)
                
                InsertResults = ET.SubElement(result_xml, "wfs:InsertResults")
                
                for result in insert_results:
                    InsertResults.append(result)
                     
                response_string = ET.tostring(result_xml)

            else:
                response_string = open("Error.xml").read()
        
        self.send_response(200, response_string, extend = {
            "Content-Type": "text/xml"
        })
        
    def do_OPTIONS(self):
        self.send_response(200, "OK")
        

class CustumServer(BaseHTTPServer.HTTPServer):
    index = 0
    
    def __init__(self, server_address, RequestHandlerClass):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)

def start_server():
    roadbalance = CustumServer(('', 9006), MainServerHandler)
    print('Starting WFS server on port 9006...')
    roadbalance.serve_forever()

if __name__ == '__main__':
    start_server()