import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import type { ConfigurationOptionPublic } from "@/client"
import DeleteConfigurationOption from "../ConfigurationOptions/DeleteConfigurationOption"
import EditConfigurationOption from "../ConfigurationOptions/EditConfigurationOption"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface ConfigurationOptionActionsMenuProps {
  configuration_option: ConfigurationOptionPublic
}

export const ConfigurationOptionActionsMenu = ({ configuration_option }: ConfigurationOptionActionsMenuProps) => {
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <EditConfigurationOption configuration_option={configuration_option} />
        <DeleteConfigurationOption configuration_option={configuration_option} />
      </MenuContent>
    </MenuRoot>
  )
}
