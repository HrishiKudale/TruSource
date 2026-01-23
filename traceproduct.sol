// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract CropTraceability {

    struct Crop {
        string cropId;
        string cropType;
        string farmerName;
        string datePlanted;
        string harvestDate;
        CropEvent[] history;
    }

    struct CropEvent {
        string status;
        string location;
        string actor;
        uint256 timestamp;
        string datePlanted;
        string harvestDate;
        string receivedDate;
        string processedDate;
        string packagingType;
    }

    mapping(string => Crop) private crops;

    event CropRegistered(string cropId, string cropType, string farmerName);
    event HarvestRecorded(string cropId, string harvestDate);
    event StatusUpdated(string cropId, string status, string location, string actor);
    event ProcessingRecorded(string cropId, string status, string processor);

    // Register a new crop by Farmer
    function registerCrop(
        string memory cropId,
        string memory cropType,
        string memory farmerName,
        string memory datePlanted
    ) public {
        require(bytes(crops[cropId].cropId).length == 0, "Crop already registered");

        Crop storage c = crops[cropId];
        c.cropId = cropId;
        c.cropType = cropType;
        c.farmerName = farmerName;
        c.datePlanted = datePlanted;

        c.history.push(CropEvent(
            "Planted",
            "Farm",
            farmerName,
            block.timestamp,
            datePlanted,
            "",
            "",
            "",
            ""
        ));
        emit CropRegistered(cropId, cropType, farmerName);
    }

    // Record harvest by Farmer
    function registerHarvest(string memory cropId, string memory harvestDate) public {
        require(bytes(crops[cropId].cropId).length != 0, "Crop not found");
        require(bytes(crops[cropId].harvestDate).length == 0, "Harvest already recorded");

        crops[cropId].harvestDate = harvestDate;

        Crop storage c = crops[cropId];
        c.history.push(CropEvent(
            "Harvested",
            "Farm",
            c.farmerName,
            block.timestamp,
            c.datePlanted,
            harvestDate,
            "",
            "",
            ""
        ));
        emit HarvestRecorded(cropId, harvestDate);
    }

    // Update status by Retailer or Owner
    function updateStatus(
        string memory cropId,
        string memory status,
        string memory location,
        string memory actor
    ) public {
        require(bytes(crops[cropId].cropId).length != 0, "Crop not found");

        Crop storage c = crops[cropId];
        c.history.push(CropEvent(
            status,
            location,
            actor,
            block.timestamp,
            c.datePlanted,
            c.harvestDate,
            "",
            "",
            ""
        ));
        emit StatusUpdated(cropId, status, location, actor);
    }

    // Register crop processing by Manufacturer
    function registerProcessing(
        string memory cropId,
        string memory receivedDate,
        string memory processedDate,
        string memory status,
        string memory packagingType,
        string memory processor
    ) public {
        require(bytes(crops[cropId].cropId).length != 0, "Crop not found");

        Crop storage c = crops[cropId];
        c.history.push(CropEvent(
            status,
            "Processing Unit",
            processor,
            block.timestamp,
            c.datePlanted,
            c.harvestDate,
            receivedDate,
            processedDate,
            packagingType
        ));
        emit ProcessingRecorded(cropId, status, processor);
    }

    // View basic crop summary
    function getCrop(string memory cropId) public view returns (
        string memory, string memory, string memory, string memory, string memory
    ) {
        Crop storage c = crops[cropId];
        return (c.cropId, c.cropType, c.farmerName, c.datePlanted, c.harvestDate);
    }

    // View full crop event history
    function getCropHistory(string memory cropId) public view returns (
        string[] memory statuses,
        string[] memory locations,
        string[] memory actors,
        uint256[] memory timestamps,
        string[] memory plantedDates,
        string[] memory harvestedDates,
        string[] memory receivedDates,
        string[] memory processedDates,
        string[] memory packagingTypes
    ) {
        Crop storage c = crops[cropId];
        uint256 len = c.history.length;

        statuses = new string[](len);
        locations = new string[](len);
        actors = new string[](len);
        timestamps = new uint256[](len);
        plantedDates = new string[](len);
        harvestedDates = new string[](len);
        receivedDates = new string[](len);
        processedDates = new string[](len);
        packagingTypes = new string[](len);

        for (uint i = 0; i < len; i++) {
            statuses[i] = c.history[i].status;
            locations[i] = c.history[i].location;
            actors[i] = c.history[i].actor;
            timestamps[i] = c.history[i].timestamp;
            plantedDates[i] = c.history[i].datePlanted;
            harvestedDates[i] = c.history[i].harvestDate;
            receivedDates[i] = c.history[i].receivedDate;
            processedDates[i] = c.history[i].processedDate;
            packagingTypes[i] = c.history[i].packagingType;
        }
    }
}
